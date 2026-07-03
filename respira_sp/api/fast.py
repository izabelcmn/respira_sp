import os
import pandas as pd
import joblib
import numpy as np
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from respira_sp.ml_logic.data import clean_data, fetch_operational_data
from respira_sp.ml_logic.preprocessor import preprocess_features
from respira_sp.params import LOCAL_DATA_PATH, LOCAL_REGISTRY_PATH

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SP_TZ = ZoneInfo("America/Sao_Paulo")

# Load trained LightGBM model once at startup
app.state.model = joblib.load(
    Path(LOCAL_REGISTRY_PATH) / "lightgbm_pm25.pkl"
)


@app.get("/")
def root():
    return {"status": "Respira SP API online"}


@app.get("/update")
def update():
    """
    Fetches fresh operational data from OpenAQ and OpenMeteo APIs.
    Saves new CSVs to data/operational/.
    Called daily by Cloud Scheduler at 00:05 America/Sao_Paulo (03:05 UTC).
    """
    api_key = os.getenv("OPENAQ_API_KEY")

    if not api_key:
        return {"error": "OPENAQ_API_KEY not set in environment."}

    try:
        df_openaq, df_openmeteo = fetch_operational_data(api_key)
        return {
            "status":         "ok",
            "rows_openaq":    len(df_openaq),
            "rows_openmeteo": len(df_openmeteo),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/forecast")
def forecast():
    """
    Returns PM2.5 forecast for the next 24 hours.
    Uses the last 30 days of operational data as historical context
    to compute lag and rolling features — exactly as done in the
    training notebook (prever_24h).

    All timestamps are UTC internally.
    Each forecast item includes both UTC and America/Sao_Paulo timestamps.
    """

    # Load latest operational data — always picks the most recent file
    data_path = Path(LOCAL_DATA_PATH) / "operational"

    openaq_files = sorted(data_path.glob("openaq_location_*.csv"))
    if not openaq_files:
        return {"error": "No OpenAQ data file found in operational folder."}
    df_openaq = pd.read_csv(openaq_files[-1])

    openmeteo_files = sorted(data_path.glob("openmeteo_operacional_*.csv"))
    if not openmeteo_files:
        return {"error": "No OpenMeteo data file found in operational folder."}
    df_openmeteo = pd.read_csv(openmeteo_files[-1])

    # Clean and merge OpenAQ + OpenMeteo
    df_clean = clean_data(df_openaq, df_openmeteo)

    # Prepare datetime index for the preprocessor
    df_clean = df_clean.rename(columns={"PM2.5": "MP2.5"})
    df_clean = df_clean.set_index("time")
    df_clean.index = pd.to_datetime(df_clean.index, utc=True)

    # Feature engineering — mirrors the training notebook
    X_processed = preprocess_features(df_clean)

    # Drop rows with NaN — initial lag rows lack sufficient historical context
    X_processed = X_processed.dropna()

    if X_processed.empty:
        return {"error": "Insufficient data to generate forecast."}

    # Forecast next 24h — mirrors prever_24h from the notebook
    # Take the last 24 rows with complete features.
    # Each row represents one hour; the model predicts PM2.5 +24h ahead.
    X_future = X_processed.iloc[-24:]
    y_pred   = app.state.model.predict(X_future)
    y_pred   = np.clip(y_pred, 0, None)  # PM2.5 cannot be negative

    # Build response payload for the frontend
    # Each item includes UTC and SP timestamps — frontend uses timestamp_sp
    forecast_series = [
        {
            "timestamp_utc": str(ts + pd.Timedelta(hours=24)),
            "timestamp_sp":  str((ts + pd.Timedelta(hours=24)).astimezone(SP_TZ)),
            "reference_hour": str(ts),
            "pm25_forecast":  round(float(val), 2)
        }
        for ts, val in zip(X_future.index, y_pred)
    ]

    # Current PM2.5 — last available real reading
    pm25_atual = df_clean["MP2.5"].dropna().iloc[-1] \
                 if df_clean["MP2.5"].notna().any() else None

    # Last updated — converted to SP for display
    last_updated_sp = df_clean.index[-1].astimezone(SP_TZ)

    return {
        "last_updated_utc": str(df_clean.index[-1]),
        "last_updated_sp":  str(last_updated_sp),
        "pm25_current":     round(float(pm25_atual), 2) if pm25_atual is not None else None,
        "forecast_24h":     forecast_series,
        "pm25_max_24h":     round(float(max(f["pm25_forecast"] for f in forecast_series)), 2),
        "pm25_min_24h":     round(float(min(f["pm25_forecast"] for f in forecast_series)), 2),
    }
