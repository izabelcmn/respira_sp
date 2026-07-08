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
    upload_file_to_gcs,
    download_latest_matching_file_from_gcs,
)
from respirasp.params import (
    LOCAL_DATA_PATH,
    LOCAL_REGISTRY_PATH,
    GCS_BUCKET_NAME,
    GCS_OPERATIONAL_PREFIX,
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

# Simple in-memory cache to avoid recomputing the forecast on every request
app.state.forecast_cache = None
app.state.forecast_cache_time = 0

# Load the trained LightGBM model once at startup
app.state.model = joblib.load(
    Path(LOCAL_REGISTRY_PATH) / "lightgbm_pm25.pkl"
)


def _openaq_data_is_valid(
    df_openaq: pd.DataFrame,
    min_recent_hours: int = 48,
    max_null_ratio: float = 0.5,
) -> tuple[bool, str]:
    """
    Data-quality gate for a freshly fetched OpenAQ dataframe.

    Prevents a broken/incomplete /update run (e.g. the pm25 sensor failing
    to return data for that day) from being promoted to "latest" and
    silently breaking /forecast. Returns (is_valid, reason).
    """
    if "pm25" not in df_openaq.columns:
        return False, "Coluna 'pm25' ausente no fetch do OpenAQ (sensor pode ter falhado)."

    if df_openaq["pm25"].dropna().empty:
        return False, "Coluna 'pm25' presente mas sem nenhum valor válido."

    recent = df_openaq.tail(min_recent_hours)
    null_ratio = recent["pm25"].isna().mean()
    if null_ratio > max_null_ratio:
        return False, (
            f"Dados de PM2.5 recentes insuficientes "
            f"({null_ratio:.0%} nulos nas últimas {min_recent_hours}h)."
        )

    return True, ""


@app.get("/")
def root():
    return {"status": "Respira SP API online"}


@app.get("/update")
def update():
    """
    Fetches fresh operational data from OpenAQ and OpenMeteo APIs.

    In local mode, CSV files are saved to data/operational/.
    In GCS mode, the latest generated CSV files are uploaded to Cloud Storage.

    Called daily by Cloud Scheduler at 00:00 America/Sao_Paulo (03:00 UTC).
    """
    api_key = os.getenv("OPENAQ_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAQ_API_KEY not set in environment.",
        )

    try:
        # Fetch and save operational data locally first
        df_openaq, df_openmeteo = fetch_operational_data(api_key)

        # Data-quality gate: don't let a broken/incomplete fetch become the
        # "latest" data served by /forecast. If this fails, nothing is
        # uploaded and /forecast keeps serving the last good file in GCS.
        is_valid, reason = _openaq_data_is_valid(df_openaq)
        if not is_valid:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Fetch do OpenAQ falhou na validação de qualidade: {reason} "
                    "O último dado operacional válido foi mantido — nada foi sobrescrito."
                ),
            )

        operational_path = Path(LOCAL_DATA_PATH) / "operational"

        # Upload the latest generated CSV files to Cloud Storage when enabled
        if USE_GCS_STORAGE:
            if not GCS_BUCKET_NAME:
                raise HTTPException(
                    status_code=500,
                    detail="GCS_BUCKET_NAME not set in environment.",
                )

            openaq_files = sorted(operational_path.glob("openaq_location_*.csv"))
            openmeteo_files = sorted(operational_path.glob("openmeteo_operacional_*.csv"))

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
                destination_blob_name=f"{GCS_OPERATIONAL_PREFIX}/{latest_openaq.name}",
            )

            upload_file_to_gcs(
                local_path=latest_openmeteo,
                bucket_name=GCS_BUCKET_NAME,
                destination_blob_name=f"{GCS_OPERATIONAL_PREFIX}/{latest_openmeteo.name}",
            )

        # Clear forecast cache after new data is collected
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/forecast")
def forecast():
    """
    Returns the PM2.5 forecast for the next 24 hours.

    In local mode, the API reads the latest CSV files from data/operational/.
    In GCS mode, the API downloads the latest CSV files from Cloud Storage
    to /tmp and then generates the forecast from them.
    """
    now = time.time()

    # Use cached forecast for 5 minutes
    if app.state.forecast_cache and now - app.state.forecast_cache_time < 300:
        return app.state.forecast_cache

    try:
        # Resolve data source: Cloud Storage or local filesystem
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
            if not openaq_files:
                raise HTTPException(
                    status_code=404,
                    detail="No OpenAQ data file found in operational folder.",
                )

            openmeteo_files = sorted(data_path.glob("openmeteo_operacional_*.csv"))
            if not openmeteo_files:
                raise HTTPException(
                    status_code=404,
                    detail="No OpenMeteo data file found in operational folder.",
                )

            openaq_file = openaq_files[-1]
            openmeteo_file = openmeteo_files[-1]

        # Read operational CSV files
        df_openaq = pd.read_csv(openaq_file)
        df_openmeteo = pd.read_csv(openmeteo_file)

        # Clean and merge OpenAQ + OpenMeteo data
        df_clean = clean_data(df_openaq, df_openmeteo)

        # Prepare datetime index for feature preprocessing
        df_clean = df_clean.rename(columns={"PM2.5": "MP2.5"})
        df_clean = df_clean.set_index("time")
        df_clean.index = pd.to_datetime(df_clean.index, utc=True)

        # Generate model features
        X_processed = preprocess_features(df_clean)
        X_processed = X_processed.dropna()

        if X_processed.empty:
            raise HTTPException(
                status_code=422,
                detail="Insufficient data to generate forecast.",
            )

        # Use the last 24 complete feature rows.
        # The model predicts PM2.5 24 hours ahead for each reference hour.
        X_future = X_processed.iloc[-24:]
        y_pred = app.state.model.predict(X_future)
        y_pred = np.clip(y_pred, 0, None)

        # Build forecast payload with both UTC and São Paulo timestamps
        forecast_series = [
            {
                "timestamp_utc": str(ts + pd.Timedelta(hours=24)),
                "timestamp_sp": str((ts + pd.Timedelta(hours=24)).astimezone(SP_TZ)),
                "reference_hour": str(ts),
                "pm25_forecast": round(float(val), 2),
            }
            for ts, val in zip(X_future.index, y_pred)
        ]

        # Get the latest observed PM2.5 value
        pm25_current = (
            df_clean["MP2.5"].dropna().iloc[-1]
            if df_clean["MP2.5"].notna().any()
            else None
        )

        last_updated_sp = df_clean.index[-1].astimezone(SP_TZ)

        response = {
            "last_updated_utc": str(df_clean.index[-1]),
            "last_updated_sp": str(last_updated_sp),
            "pm25_current": round(float(pm25_current), 2)
            if pm25_current is not None
            else None,
            "forecast_24h": forecast_series,
            "pm25_max_24h": round(
                float(max(f["pm25_forecast"] for f in forecast_series)), 2
            ),
            "pm25_min_24h": round(
                float(min(f["pm25_forecast"] for f in forecast_series)), 2
            ),
        }

        # Store forecast response in memory cache
        app.state.forecast_cache = response
        app.state.forecast_cache_time = now

        return response

    except HTTPException:
        raise

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
