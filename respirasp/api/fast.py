import os
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from respirasp.ml_logic.data import clean_data, fetch_operational_data
from respirasp.ml_logic.preprocessor import preprocess_features
from respirasp.ml_logic.gcs_storage import (
    download_json_from_gcs,
    download_latest_matching_file_from_gcs,
    upload_file_to_gcs,
    upload_json_to_gcs,
)
from respirasp.params import (
    GCS_BUCKET_NAME,
    GCS_OPERATIONAL_PREFIX,
    LOCAL_DATA_PATH,
    LOCAL_REGISTRY_PATH,
    USE_GCS_STORAGE,
)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SP_TZ = ZoneInfo("America/Sao_Paulo")
FORECAST_CACHE_TTL_SECONDS = 300
MAX_FEATURE_DELAY_HOURS = 6

FORECAST_BLOB_NAME = (
    f"{GCS_OPERATIONAL_PREFIX.rstrip('/')}/forecast/latest_forecast.json"
)

app.state.forecast_cache = None
app.state.forecast_cache_time = 0

app.state.model = joblib.load(
    Path(LOCAL_REGISTRY_PATH) / "lightgbm_pm25.pkl"
)


def _expected_operational_end_utc() -> pd.Timestamp:
    """Return the expected final hourly timestamp for the previous day."""
    now_sp = pd.Timestamp.now(tz=SP_TZ)
    previous_day_23_sp = now_sp.normalize() - pd.Timedelta(hours=1)
    return previous_day_23_sp.tz_convert("UTC")


def _openaq_data_is_valid(
    df_openaq: pd.DataFrame,
    max_staleness_hours: int = 6,
    recent_window_hours: int = 48,
    min_valid_ratio: float = 0.75,
) -> tuple[bool, str]:
    """Validate recency and hourly coverage of fetched PM2.5 data."""
    required_columns = {"time", "pm25"}
    missing_columns = required_columns.difference(df_openaq.columns)

    if missing_columns:
        return False, (
            "Missing required OpenAQ columns: "
            + ", ".join(sorted(missing_columns))
            + "."
        )

    df = df_openaq.copy()
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df["pm25"] = pd.to_numeric(df["pm25"], errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time")

    if df.empty:
        return False, "The OpenAQ dataframe contains no valid timestamps."

    valid_pm25 = df.dropna(subset=["pm25"])

    if valid_pm25.empty:
        return False, "OpenAQ returned no valid PM2.5 observations."

    latest_pm25_time = valid_pm25["time"].max()
    expected_end = _expected_operational_end_utc()

    staleness_hours = max(
        0.0,
        (expected_end - latest_pm25_time).total_seconds() / 3600,
    )

    if staleness_hours > max_staleness_hours:
        return False, (
            "The latest valid PM2.5 observation is "
            f"{staleness_hours:.1f} hours behind the expected operational end "
            f"({expected_end})."
        )

    recent_start = expected_end - pd.Timedelta(hours=recent_window_hours - 1)
    recent = df[
        (df["time"] >= recent_start)
        & (df["time"] <= expected_end)
    ]

    if recent.empty:
        return False, (
            f"No OpenAQ observations were found in the latest "
            f"{recent_window_hours}-hour validation window."
        )

    recent_hourly = (
        recent.set_index("time")["pm25"]
        .resample("1h")
        .mean()
        .reindex(
            pd.date_range(
                start=recent_start.floor("h"),
                end=expected_end.floor("h"),
                freq="1h",
                tz="UTC",
            )
        )
    )

    valid_ratio = float(recent_hourly.notna().mean())

    if valid_ratio < min_valid_ratio:
        return False, (
            f"Only {valid_ratio:.0%} of the expected PM2.5 hours are valid "
            f"in the latest {recent_window_hours} hours."
        )

    return True, ""


def _feature_rows_are_contiguous(X_future: pd.DataFrame) -> bool:
    """Check whether the selected feature rows form a continuous 24-hour window."""
    if len(X_future) != 24:
        return False

    expected_index = pd.date_range(
        start=X_future.index[0],
        periods=24,
        freq="1h",
        tz=X_future.index.tz,
    )

    return X_future.index.equals(expected_index)


def _load_fallback_forecast(reason: str) -> dict:
    """Load the latest valid forecast from GCS and mark it as fallback."""
    if not USE_GCS_STORAGE or not GCS_BUCKET_NAME:
        raise HTTPException(status_code=503, detail=reason)

    try:
        fallback = download_json_from_gcs(
            bucket_name=GCS_BUCKET_NAME,
            blob_name=FORECAST_BLOB_NAME,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail=(
                f"{reason} No previously valid forecast is available "
                "in Cloud Storage."
            ),
        )

    fallback["forecast_status"] = "fallback"
    fallback["fallback_reason"] = reason
    fallback["served_at_utc"] = str(pd.Timestamp.now(tz="UTC"))

    app.state.forecast_cache = fallback
    app.state.forecast_cache_time = time.time()

    return fallback


@app.get("/")
def root():
    return {"status": "Respira SP API online"}


@app.get("/update")
def update():
    """Fetch, validate and persist operational OpenAQ/OpenMeteo data."""
    api_key = os.getenv("OPENAQ_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAQ_API_KEY not set in environment.",
        )

    try:
        df_openaq, df_openmeteo = fetch_operational_data(api_key)

        is_valid, reason = _openaq_data_is_valid(df_openaq)

        if not is_valid:
            raise HTTPException(
                status_code=502,
                detail=(
                    "OpenAQ data failed the quality validation: "
                    f"{reason} The latest valid operational files were kept."
                ),
            )

        operational_path = Path(LOCAL_DATA_PATH) / "operational"

        if USE_GCS_STORAGE:
            if not GCS_BUCKET_NAME:
                raise HTTPException(
                    status_code=500,
                    detail="GCS_BUCKET_NAME not set in environment.",
                )

            openaq_files = sorted(
                operational_path.glob("openaq_location_*.csv")
            )
            openmeteo_files = sorted(
                operational_path.glob("openmeteo_operacional_*.csv")
            )

            if not openaq_files:
                raise HTTPException(
                    status_code=500,
                    detail="No OpenAQ CSV found after update.",
                )

            if not openmeteo_files:
                raise HTTPException(
                    status_code=500,
                    detail="No OpenMeteo CSV found after update.",
                )

            latest_openaq = openaq_files[-1]
            latest_openmeteo = openmeteo_files[-1]

            upload_file_to_gcs(
                local_path=latest_openaq,
                bucket_name=GCS_BUCKET_NAME,
                destination_blob_name=(
                    f"{GCS_OPERATIONAL_PREFIX.rstrip('/')}/"
                    f"{latest_openaq.name}"
                ),
            )

            upload_file_to_gcs(
                local_path=latest_openmeteo,
                bucket_name=GCS_BUCKET_NAME,
                destination_blob_name=(
                    f"{GCS_OPERATIONAL_PREFIX.rstrip('/')}/"
                    f"{latest_openmeteo.name}"
                ),
            )

        app.state.forecast_cache = None
        app.state.forecast_cache_time = 0

        return {
            "status": "ok",
            "storage": "gcs" if USE_GCS_STORAGE else "local",
            "rows_openaq": len(df_openaq),
            "rows_openmeteo": len(df_openmeteo),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/forecast")
def forecast():
    """Return a live 24-hour PM2.5 forecast or the last valid GCS fallback."""
    now = time.time()

    if (
        app.state.forecast_cache
        and now - app.state.forecast_cache_time
        < FORECAST_CACHE_TTL_SECONDS
    ):
        return app.state.forecast_cache

    try:
        if USE_GCS_STORAGE:
            if not GCS_BUCKET_NAME:
                raise HTTPException(
                    status_code=500,
                    detail="GCS_BUCKET_NAME not set in environment.",
                )

            runtime_data_path = Path("/tmp") / "respirasp" / "operational"

            openaq_file = download_latest_matching_file_from_gcs(
                bucket_name=GCS_BUCKET_NAME,
                prefix=GCS_OPERATIONAL_PREFIX,
                filename_prefix="openaq_location_",
                destination_dir=runtime_data_path,
            )

            openmeteo_file = download_latest_matching_file_from_gcs(
                bucket_name=GCS_BUCKET_NAME,
                prefix=GCS_OPERATIONAL_PREFIX,
                filename_prefix="openmeteo_operacional_",
                destination_dir=runtime_data_path,
            )

        else:
            data_path = Path(LOCAL_DATA_PATH) / "operational"
            openaq_files = sorted(data_path.glob("openaq_location_*.csv"))
            openmeteo_files = sorted(
                data_path.glob("openmeteo_operacional_*.csv")
            )

            if not openaq_files:
                raise HTTPException(
                    status_code=404,
                    detail="No OpenAQ data file found in operational folder.",
                )

            if not openmeteo_files:
                raise HTTPException(
                    status_code=404,
                    detail="No OpenMeteo data file found in operational folder.",
                )

            openaq_file = openaq_files[-1]
            openmeteo_file = openmeteo_files[-1]

        df_openaq = pd.read_csv(openaq_file)
        df_openmeteo = pd.read_csv(openmeteo_file)

        df_clean = clean_data(df_openaq, df_openmeteo)
        df_clean = df_clean.rename(columns={"PM2.5": "MP2.5"})
        df_clean = df_clean.set_index("time")
        df_clean.index = pd.to_datetime(df_clean.index, utc=True)
        df_clean = df_clean.sort_index()

        X_processed = preprocess_features(df_clean).dropna()

        if X_processed.empty:
            return _load_fallback_forecast(
                "Insufficient complete feature rows to generate a forecast."
            )

        latest_data_time = df_clean.index.max()
        latest_feature_time = X_processed.index.max()

        feature_delay_hours = max(
            0.0,
            (latest_data_time - latest_feature_time).total_seconds() / 3600,
        )

        if feature_delay_hours > MAX_FEATURE_DELAY_HOURS:
            return _load_fallback_forecast(
                "Recent PM2.5 observations are insufficient to generate an "
                "up-to-date forecast. The latest complete feature row is "
                f"{feature_delay_hours:.1f} hours behind the latest dataset "
                f"timestamp ({latest_data_time})."
            )

        X_future = X_processed.iloc[-24:]

        if not _feature_rows_are_contiguous(X_future):
            return _load_fallback_forecast(
                "The latest complete model features do not form a continuous "
                "24-hour window."
            )

        y_pred = app.state.model.predict(X_future)
        y_pred = np.clip(y_pred, 0, None)

        forecast_series = [
            {
                "timestamp_utc": str(ts + pd.Timedelta(hours=24)),
                "timestamp_sp": str(
                    (ts + pd.Timedelta(hours=24)).astimezone(SP_TZ)
                ),
                "reference_hour": str(ts),
                "pm25_forecast": round(float(value), 2),
            }
            for ts, value in zip(X_future.index, y_pred)
        ]

        valid_pm25 = df_clean["MP2.5"].dropna()
        pm25_current = valid_pm25.iloc[-1] if not valid_pm25.empty else None
        pm25_current_time = (
            valid_pm25.index[-1] if not valid_pm25.empty else None
        )

        generated_at_utc = pd.Timestamp.now(tz="UTC")

        response = {
            "forecast_status": "live",
            "generated_at_utc": str(generated_at_utc),
            "source_openaq_file": Path(openaq_file).name,
            "source_openmeteo_file": Path(openmeteo_file).name,
            "last_updated_utc": str(latest_data_time),
            "last_updated_sp": str(latest_data_time.astimezone(SP_TZ)),
            "latest_complete_feature_utc": str(latest_feature_time),
            "feature_delay_hours": round(float(feature_delay_hours), 1),
            "pm25_current": (
                round(float(pm25_current), 2)
                if pm25_current is not None
                else None
            ),
            "pm25_current_timestamp_utc": (
                str(pm25_current_time)
                if pm25_current_time is not None
                else None
            ),
            "pm25_current_timestamp_sp": (
                str(pm25_current_time.astimezone(SP_TZ))
                if pm25_current_time is not None
                else None
            ),
            "forecast_24h": forecast_series,
            "pm25_max_24h": round(
                float(max(item["pm25_forecast"] for item in forecast_series)),
                2,
            ),
            "pm25_min_24h": round(
                float(min(item["pm25_forecast"] for item in forecast_series)),
                2,
            ),
        }

        if USE_GCS_STORAGE and GCS_BUCKET_NAME:
            upload_json_to_gcs(
                payload=response,
                bucket_name=GCS_BUCKET_NAME,
                destination_blob_name=FORECAST_BLOB_NAME,
            )

        app.state.forecast_cache = response
        app.state.forecast_cache_time = now

        return response

    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
