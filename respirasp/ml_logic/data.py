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

    r = requests.get(
        f"{BASE_URL}/locations/{location_id}/sensors",
        headers=headers
    )
    r.raise_for_status()
    sensors = pd.json_normalize(r.json()["results"])

    def _fetch_sensor(sensor_id: int) -> pd.DataFrame:
        page, limit, dados = 1, 1000, []
        while True:
            resp = requests.get(
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
            print(f"  Warning — sensor {nome}: {e}")

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

    aq["time"]  = pd.to_datetime(aq["time"], utc=True).dt.floor("h")
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

    print(f"✅ data cleaned — {len(df)} linhas | "
          f"range: {df['time'].min()} → {df['time'].max()} | "
          f"PM2.5 NaN: {df['PM2.5'].isna().sum()}")

    return df
