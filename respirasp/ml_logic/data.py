import pandas as pd
import requests
import openmeteo_requests
import requests_cache
from retry_requests import retry
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from respirasp.params import DTYPES_RAW, COLUMN_NAMES_RAW, LOCAL_DATA_PATH


def fetch_operational_data(api_key: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fetches the last 30 days of operational data from OpenAQ and OpenMeteo.
    Saves CSVs to data/operational/ and returns both DataFrames.

    Date window is calculated in America/Sao_Paulo to match the user's day,
    then converted to UTC for all API calls and internal timestamps.

    Returns:
        df_openaq    — wide format with columns: time, pm25 (UTC)
        df_openmeteo — columns: time, temperature_2m, relative_humidity_2m,
                       precipitation, wind_speed_10m (UTC)
    """

    #  Date range: calculated in SP, converted to UTC for APIs ─
    SP_TZ     = ZoneInfo("America/Sao_Paulo")
    today_sp  = datetime.now(SP_TZ)
    date_to   = today_sp - timedelta(days=1)    # yesterday in SP
    date_from = date_to  - timedelta(days=29)   # 30-day window in SP

    # Convert SP boundaries to UTC for API calls
    date_from_utc = date_from.replace(
        hour=0, minute=0, second=0, microsecond=0
    ).astimezone(timezone.utc)

    date_to_utc = date_to.replace(
        hour=23, minute=59, second=59, microsecond=0
    ).astimezone(timezone.utc)

    date_from_str = date_from_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    date_to_str   = date_to_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Date string for filenames — SP date (what the user sees)
    date_str = date_to.strftime("%Y%m%d")

    # OpenMeteo uses date only — SP date
    date_from_meteo = date_from.strftime("%Y-%m-%d")
    date_to_meteo   = date_to.strftime("%Y-%m-%d")

    print(f"  Fetching data for SP window: "
          f"{date_from.strftime('%Y-%m-%d')} → {date_to.strftime('%Y-%m-%d')} "
          f"(UTC: {date_from_str} → {date_to_str})")

    #  1. OpenAQ
    BASE_URL    = "https://api.openaq.org/v3"
    location_id = 6139516
    headers     = {"X-API-Key": api_key}

    # Retry-enabled session — mirrors the OpenMeteo client below.
    # Without this, a single transient timeout/rate-limit on the OpenAQ side
    # silently drops that sensor (e.g. pm25) for the whole day's fetch,
    # instead of being retried.
    openaq_session = retry(requests.Session(), retries=5, backoff_factor=0.3)

    r = openaq_session.get(
        f"{BASE_URL}/locations/{location_id}/sensors",
        headers=headers
    )
    r.raise_for_status()
    sensors = pd.json_normalize(r.json()["results"])

    def _fetch_sensor(sensor_id: int) -> pd.DataFrame:
        page, limit, dados = 1, 1000, []
        while True:
            resp = openaq_session.get(
                f"{BASE_URL}/sensors/{sensor_id}/hours",
                headers=headers,
                params={
                    "datetime_from": date_from_str,
                    "datetime_to":   date_to_str,
                    "limit":         limit,
                    "page":          page,
                }
            )
            resp.raise_for_status()
            js      = resp.json()
            results = js.get("results", [])
            if not results:
                break
            dados.extend(results)
            if page * limit >= js.get("meta", {}).get("found", 0):
                break
            page += 1
        return pd.json_normalize(dados)

    # Build wide DataFrame — one column per sensor, UTC timestamps
    series = {}
    for _, row in sensors.iterrows():
        sensor_id = row["id"]
        nome      = row["parameter.name"]
        print(f"  Fetching OpenAQ sensor: {nome}")
        try:
            df_tmp = _fetch_sensor(sensor_id)
            if df_tmp.empty:
                continue
            # Always use UTC field — never local
            s = pd.Series(
                df_tmp["value"].values,
                index=pd.to_datetime(
                    df_tmp["period.datetimeFrom.utc"], utc=True
                ).dt.floor("h"),
                name=nome
            )
            s = s[~s.index.duplicated(keep="first")]
            series[nome] = s
        except Exception as e:
            # PM2.5 is the target variable — flag its failure loudly so it
            # doesn't get missed in Cloud Run logs like a routine warning.
            level = "CRITICAL" if nome == "pm25" else "Warning"
            print(f"  {level} — sensor {nome} failed even after retries: {e}")

    df_openaq = pd.DataFrame(series).sort_index()
    df_openaq.index.name = "time"
    df_openaq = df_openaq.reset_index()

    openaq_path = Path(LOCAL_DATA_PATH) / "operational" / \
                  f"openaq_location_{location_id}_{date_str}.csv"
    df_openaq.to_csv(openaq_path, index=False, encoding="utf-8")
    print(f"✅ OpenAQ saved: {openaq_path.name} ({len(df_openaq)} rows)")

    #  2. OpenMeteo
    cache_session    = requests_cache.CachedSession(".cache", expire_after=-1)
    retry_session    = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo_client = openmeteo_requests.Client(session=retry_session)

    params = {
        "latitude":   -23.6473149,
        "longitude":  -46.6643635,
        "start_date": date_from_meteo,
        "end_date":   date_to_meteo,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "wind_speed_10m",
        ],
        "timezone": "UTC",  # Force UTC — critical for Cloud Run
    }

    response = openmeteo_client.weather_api(
        "https://archive-api.open-meteo.com/v1/archive",
        params=params
    )[0]
    hourly = response.Hourly()

    df_openmeteo = pd.DataFrame({
        "time": pd.date_range(
            start=pd.to_datetime(hourly.Time(),    unit="s", utc=True),
            end=  pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        ),
        "temperature_2m":       hourly.Variables(0).ValuesAsNumpy(),
        "relative_humidity_2m": hourly.Variables(1).ValuesAsNumpy(),
        "precipitation":        hourly.Variables(2).ValuesAsNumpy(),
        "wind_speed_10m":       hourly.Variables(3).ValuesAsNumpy(),
    })

    # Keep UTC — do NOT convert to America/Sao_Paulo
    df_openmeteo["time"] = pd.to_datetime(df_openmeteo["time"], utc=True)
    df_openmeteo = df_openmeteo.sort_values("time").reset_index(drop=True)

    openmeteo_path = Path(LOCAL_DATA_PATH) / "operational" / \
                     f"openmeteo_operacional_{date_str}.csv"
    df_openmeteo.to_csv(openmeteo_path, index=False, encoding="utf-8")
    print(f"✅ OpenMeteo saved: {openmeteo_path.name} ({len(df_openmeteo)} rows)")

    print(f"✅ fetch_operational_data complete — "
          f"OpenAQ: {len(df_openaq)} rows | OpenMeteo: {len(df_openmeteo)} rows")

    return df_openaq, df_openmeteo



def apply_pm25_strategy_3(
    df: pd.DataFrame,
    target_col: str = "PM2.5",
    time_col: str = "time",
    max_temporal_gap_hours: int = 12,
) -> pd.DataFrame:
    """
    Applies the same missing-value strategy used by the selected LightGBM model:

    1. Interpolate only short internal PM2.5 gaps of up to 12 consecutive hours
       using time-based interpolation.
    2. Fill remaining PM2.5 gaps with the seasonal mean for the same
       month + day of week + hour.

    The function does not add helper columns to the returned dataframe, so the
    feature schema expected by the trained model remains unchanged.
    """
    if time_col not in df.columns:
        raise ValueError(f"Column '{time_col}' not found in dataframe.")

    if target_col not in df.columns:
        raise ValueError(f"Column '{target_col}' not found in dataframe.")

    result = df.copy()
    result[time_col] = pd.to_datetime(
        result[time_col],
        utc=True,
        errors="coerce",
    )

    if result[time_col].isna().any():
        raise ValueError(
            f"Column '{time_col}' contains invalid timestamps."
        )

    result[target_col] = pd.to_numeric(
        result[target_col],
        errors="coerce",
    )

    result = (
        result.sort_values(time_col)
        .drop_duplicates(subset=[time_col], keep="last")
        .set_index(time_col)
    )

    if not result.index.is_monotonic_increasing:
        result = result.sort_index()

    missing_before = int(result[target_col].isna().sum())

    # Strategy 2 step: interpolate only short internal gaps (<= 12h).
    original_series = result[target_col].copy()
    interpolated_series = original_series.interpolate(
        method="time",
        limit_area="inside",
    )

    missing_mask = original_series.isna()

    if missing_mask.any():
        gap_groups = missing_mask.ne(missing_mask.shift()).cumsum()

        for _, gap_mask in missing_mask.groupby(gap_groups):
            gap_index = gap_mask.index[gap_mask]

            if len(gap_index) == 0:
                continue

            gap_start = gap_index[0]
            gap_end = gap_index[-1]
            gap_length = len(gap_index)

            previous_position = result.index.get_loc(gap_start) - 1
            next_position = result.index.get_loc(gap_end) + 1

            is_internal_gap = (
                previous_position >= 0
                and next_position < len(result)
                and pd.notna(original_series.iloc[previous_position])
                and pd.notna(original_series.iloc[next_position])
            )

            if is_internal_gap and gap_length <= max_temporal_gap_hours:
                result.loc[gap_index, target_col] = interpolated_series.loc[
                    gap_index
                ]

    missing_after_temporal = int(result[target_col].isna().sum())

    # Strategy 3 step: seasonal mean by month + weekday + hour.
    if missing_after_temporal > 0:
        seasonal_keys = pd.DataFrame(
            {
                "month": result.index.month,
                "day_of_week": result.index.dayofweek,
                "hour": result.index.hour,
                target_col: result[target_col].values,
            },
            index=result.index,
        )

        seasonal_mean = (
            seasonal_keys
            .groupby(
                ["month", "day_of_week", "hour"],
                dropna=False,
            )[target_col]
            .transform("mean")
        )

        result[target_col] = result[target_col].fillna(seasonal_mean)

    missing_after_seasonal = int(result[target_col].isna().sum())

    result[target_col] = result[target_col].astype("float32")
    result = result.reset_index()

    print(
        "✅ PM2.5 strategy 3 applied — "
        f"missing before: {missing_before} | "
        f"after temporal interpolation: {missing_after_temporal} | "
        f"after seasonal imputation: {missing_after_seasonal}"
    )

    if missing_after_seasonal > 0:
        print(
            "⚠️ Some PM2.5 values could not be imputed because no valid "
            "seasonal mean was available for the same month, weekday and hour."
        )

    return result

def clean_data(df_openaq: pd.DataFrame, df_openmeteo: pd.DataFrame) -> pd.DataFrame:
    """
    Receives raw data from OpenAQ and OpenMeteo separately,
    merges them, and applies data quality measures.

    OpenAQ format expected: wide, columns [time, pm25, ...]
    OpenMeteo format expected: columns [time, temperature_2m, ...]
    All timestamps must be UTC.
    """

    #  OpenAQ
    aq = df_openaq.copy()

    aq["time"] = pd.to_datetime(aq["time"], utc=True).dt.floor("h")

    # Defensive check: if this ever runs on a file where the pm25 sensor
    # failed to come through, fail with a clear message instead of a raw
    # KeyError. The main safeguard is the quality gate in fast.py's /update
    # (which should stop a bad file from ever reaching here) — this is the
    # fallback in case that gate is bypassed (e.g. local mode, manual file).
    if "pm25" not in aq.columns:
        raise ValueError(
            "Coluna 'pm25' ausente no arquivo operacional do OpenAQ — "
            "o sensor de PM2.5 provavelmente falhou na coleta. "
            "Verifique o /update mais recente."
        )

    aq["PM2.5"] = pd.to_numeric(aq["pm25"], errors="coerce").astype("float32")
    aq = aq[["time", "PM2.5"]].copy()
    aq = aq.groupby("time", as_index=False)["PM2.5"].mean()

    #  OpenMeteo
    met = df_openmeteo.copy()

    met["time"] = pd.to_datetime(met["time"], utc=True).dt.floor("h")
    for col in ["temperature_2m", "relative_humidity_2m",
                "precipitation", "wind_speed_10m"]:
        met[col] = met[col].astype("float32")
    met = met.drop_duplicates(subset=["time"], keep="first")

    #  Merge
    df = met.merge(aq, on="time", how="left")
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.astype({k: v for k, v in DTYPES_RAW.items() if k != "time"})

    #  Data Quality
    df = df.dropna(subset=["temperature_2m", "relative_humidity_2m",
                            "precipitation", "wind_speed_10m"])
    df = df[COLUMN_NAMES_RAW]
    df = df.sort_values("time").reset_index(drop=True)

    # Apply the same missing-value treatment used during training of the
    # selected LightGBM model: temporal interpolation for gaps <= 12h,
    # followed by seasonal mean imputation for remaining gaps.
    df = apply_pm25_strategy_3(df)

    print(f"✅ data cleaned — {len(df)} linhas | "
          f"range: {df['time'].min()} → {df['time'].max()} | "
          f"PM2.5 NaN: {df['PM2.5'].isna().sum()}")

    return df
