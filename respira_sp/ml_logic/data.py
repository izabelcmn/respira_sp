import pandas as pd

from colorama import Fore, Style
from pathlib import Path
from respira_sp.params import DTYPES_RAW, COLUMN_NAMES_RAW

def clean_data(df_openaq: pd.DataFrame, df_openmeteo: pd.DataFrame) -> pd.DataFrame:
    """
    Receives raw data from OpenAQ and OpenMeteo separately,
    merges them, and applies data quality measures:
    - Pivots OpenAQ data from long to wide format and extracts PM2.5
    - Converts time zones to UTC
    - Merges based on hourly timestamps
    - Applies correct data types
    - Removes temporal duplicates
    - Removes rows lacking meteorological variables
    - Retains NaNs for PM2.5 (the model was trained with gaps)
    - Ensures temporal ordering
    """

    # ── OpenAQ ──────────────────────────────────────────────────────────
    aq = df_openaq.copy()

    # Filtrar só pm25 e extrair timestamp UTC
    aq = aq[aq["parameter"] == "pm25"][["datetimeUtc", "value"]].copy()
    aq = aq.rename(columns={"datetimeUtc": "time", "value": "PM2.5"})
    aq["time"] = pd.to_datetime(aq["time"], utc=True).dt.floor("h")
    aq["PM2.5"] = pd.to_numeric(aq["PM2.5"], errors="coerce").astype("float32")

    # Remover duplicatas — média se houver mais de uma leitura por hora
    aq = aq.groupby("time", as_index=False)["PM2.5"].mean()

    # ── OpenMeteo ────────────────────────────────────────────────────────
    met = df_openmeteo.copy()

    met["time"] = pd.to_datetime(met["time"], utc=True).dt.floor("h")
    for col in ["temperature_2m", "relative_humidity_2m",
                "precipitation", "wind_speed_10m"]:
        met[col] = met[col].astype("float32")

    # Remover duplicatas temporais
    met = met.drop_duplicates(subset=["time"], keep="first")

    # ── Merge ─────────────────────────────────────────────────────────────
    # Left join no OpenMeteo — garante que temos variáveis meteorológicas
    # PM2.5 pode ficar NaN onde não há leitura do OpenAQ
    df = met.merge(aq, on="time", how="left")
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.astype({k: v for k, v in DTYPES_RAW.items() if k != "time"})

    # ── Data Quality ──────────────────────────────────────────────────────
    # Remover linhas sem variáveis meteorológicas
    df = df.dropna(subset=["temperature_2m", "relative_humidity_2m",
                            "precipitation", "wind_speed_10m"])

    # Garantir colunas na ordem correta
    df = df[COLUMN_NAMES_RAW]

    # Ordenar por tempo
    df = df.sort_values("time").reset_index(drop=True)

    print(f"✅ data cleaned — {len(df)} linhas | "
          f"range: {df['time'].min()} → {df['time'].max()} | "
          f"PM2.5 NaN: {df['PM2.5'].isna().sum()}")

    return df
