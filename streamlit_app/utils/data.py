"""
utils/data.py
"""

from __future__ import annotations
import os
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st


APP_DIR  = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_DIR.parent
MODELS_DIR = Path(os.getenv("RESPIRA_MODELS_DIR", REPO_ROOT / "models"))
OP_DIR     = Path(os.getenv("RESPIRA_OP_DIR",     REPO_ROOT / "data" / "operational"))
DATA_DIR   = APP_DIR / "data"

LGBM_MODEL    = MODELS_DIR / "lightgbm_pm25.pkl"
LGBM_FEATURES = MODELS_DIR / "lightgbm_features.pkl"

HIST_CSV = DATA_DIR / "pm25_2013_2019_interp_12h_media_sazonal_all_features.csv"

TARGET_CANDIDATES = ["MP2.5", "PM2.5", "MP2_5", "mp2.5"]

STATION = "Congonhas"
TRAIN_PERIOD = "2016–2019"
# --------------------------------------------------------------------------- #
# REGISTROS DE MÉTRICAS
# Separamos OPERACIONAL (2026, LightGBM) de BACKTEST (2019, walk-forward) de
# propósito: misturar os dois R² engana a banca (regimes de avaliação diferentes).
# --------------------------------------------------------------------------- #
# Métricas REAIS do seu notebook (avaliação 2026-06-23, 24h):
LGBM_OPERATIONAL = {
    "mae": 6.725, "rmse": 8.174, "r2": 0.1706,
    "mbe": 2.474, "nmae": 70.54, "mape": 414.07,
    "mae_val2018": 4.14,                 # âncora: MAE na validação 2018
    "mean_obs": 9.53,                    # média observada na janela (ar limpo)
    "note": "Generalização 7 anos à frente; janela de ar limpo derruba R²/MAPE.",
}

# Backtest histórico (walk-forward em 2019) — contexto, NÃO comparável ao acima.
BACKTEST_2019 = {
    "XGBoost":          {"r2": 0.452, "note": "Melhor R² no backtest 2019."},
    "N-HiTS (refit)":   {"r2": 0.390, "note": "Só covariáveis passadas → viés diurno."},
    "LSTM 5.9K":        {"r2": 0.386, "note": "Baseline enxuto."},
    "LSTM 53K (tuned)": {"r2": 0.385, "note": "Mais capacidade, ganho marginal."},
    "N-HiTS (1ª run)":  {"r2": 0.373, "note": "Antes do refit."},
    "SARIMAX":          {"r2": 0.340, "note": "Linha de base estatística."},
}



# LightGBM — carga do modelo (cache_resource: objeto vive entre reruns)
@st.cache_resource(show_spinner=False)
def load_lgbm():
    """
    Carrega (model, features) do disco. Devolve (None, None) se faltar arquivo
    ou se o lightgbm/joblib não estiverem instalados — aí o app usa o fallback.
    """
    if not (LGBM_MODEL.exists() and LGBM_FEATURES.exists()):
        return None, None
    try:
        import joblib
        model = joblib.load(LGBM_MODEL)
        features = joblib.load(LGBM_FEATURES)
        return model, list(features)
    except Exception as e:               # lightgbm ausente, pickle incompatível, etc.
        st.warning(f"Não consegui carregar o LightGBM ({e}). Usando fallback sintético.")
        return None, None


@st.cache_data(show_spinner=False)
def load_operational() -> pd.DataFrame | None:
    """
    Lê o CSV operacional mais recente de data/operational/ (índice datetime UTC).
    Faz glob por 'dados_features*.csv'; se não achar, tenta qualquer .csv.
    Devolve None se a pasta estiver vazia.
    """
    if not OP_DIR.exists():
        return None
    candidates = sorted(OP_DIR.glob("dados_features*.csv")) or sorted(OP_DIR.glob("*.csv"))
    if not candidates:
        return None
    df = pd.read_csv(candidates[-1], index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()
    # Padroniza o nome do alvo para 'MP2.5' (já é o padrão, mas garantimos).
    for cand in TARGET_CANDIDATES:
        if cand in df.columns and cand != "MP2.5":
            df = df.rename(columns={cand: "MP2.5"})
    return df


def _metrics(y_real: pd.Series, y_pred: pd.Series) -> dict:
    """Calcula as mesmas métricas do notebook (MAPE incluído, mas a flagamos)."""
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    yr, yp = y_real.values, y_pred.values
    mae = mean_absolute_error(yr, yp)
    rmse = float(np.sqrt(mean_squared_error(yr, yp)))
    r2 = r2_score(yr, yp)
    mbe = float((yp - yr).mean())
    mean_obs = float(yr.mean())
    nmae = 100 * mae / mean_obs if mean_obs else float("nan")
    nz = yr != 0
    mape = float(100 * (np.abs((yr[nz] - yp[nz]) / yr[nz])).mean()) if nz.any() else float("nan")
    return {"mae": mae, "rmse": rmse, "r2": r2, "mbe": mbe,
            "nmae": nmae, "mape": mape, "mean_obs": mean_obs}


def lightgbm_forecast(n: int = 24, cut: str | None = None) -> dict:
    """
    Roda o LightGBM ao vivo sobre o CSV operacional e devolve um dicionário:
        {
          "source": "lightgbm" | "synthetic",
          "forecast": DataFrame[timestamp, yhat, y_real],   # y_real pode ter NaN
          "context":  Series PM2.5 das 72h antes do corte (p/ o gráfico),
          "cut":      Timestamp do corte,
          "metrics":  dict (se houver y_real) ou None,
        }

    Estratégia do corte: se 'cut' não for passado, escolhemos a ÚLTIMA janela de
    n horas que tenha features completas — assim o app sempre mostra algo, e quando
    há MP2.5 observado nessa janela, conseguimos métricas e o overlay observado×previsto.
    """
    model, features = load_lgbm()
    df = load_operational()

    # Sem modelo ou sem dados -> previsão sintética (app abre mesmo assim).
    if model is None or df is None or not set(features).issubset(df.columns):
        return _synthetic_forecast(n)

    # Linhas com todas as features presentes (evita NaN no predict).
    valid = df.dropna(subset=features)
    if len(valid) < n:
        return _synthetic_forecast(n)

    if cut is not None:
        cut_ts = pd.Timestamp(cut)
        if cut_ts.tzinfo is None:
            cut_ts = cut_ts.tz_localize("UTC")
        alvo = valid[valid.index > cut_ts].iloc[:n]
    else:
        alvo = valid.iloc[-n:]                       # última janela disponível
        cut_ts = valid.index[valid.index.get_loc(alvo.index[0]) - 1] \
                 if valid.index.get_loc(alvo.index[0]) > 0 else alvo.index[0]

    X = alvo[features]
    yhat = pd.Series(model.predict(X), index=alvo.index, name="yhat")

    # y_real quando o alvo já foi observado (permite métricas).
    y_real = alvo["MP2.5"] if "MP2.5" in alvo.columns else pd.Series(index=alvo.index, dtype=float)

    fc = pd.DataFrame({"timestamp": alvo.index, "yhat": yhat.values})
    fc["y_real"] = y_real.values

    # Contexto: 72h observadas antes do corte.
    ctx = df.loc[df.index <= cut_ts, "MP2.5"].dropna().iloc[-72:]

    # Métricas só se houver observado suficiente na janela.
    metrics = None
    real_mask = fc["y_real"].notna()
    if real_mask.sum() >= max(3, n // 2):
        metrics = _metrics(fc.loc[real_mask, "y_real"], fc.loc[real_mask, "yhat"])

    return {"source": "lightgbm", "forecast": fc, "context": ctx,
            "cut": cut_ts, "metrics": metrics}


# Fallbacks sintéticos (para o app abrir sem nenhum arquivo)
def _synthetic_forecast(n: int = 24) -> dict:
    """Previsão sintética de n horas, com observado fictício para a demo."""
    end = pd.Timestamp.utcnow().floor("h")
    idx = pd.date_range(end, periods=n, freq="h")
    h = idx.hour.values
    diurnal = 8 * np.sin((h - 7) / 24 * 2 * np.pi) + 6 * np.sin((h - 19) / 12 * 2 * np.pi)
    yhat = np.clip(12 + diurnal + np.random.normal(0, 2, n), 2, None)
    y_real = np.clip(yhat + np.random.normal(0, 3, n), 2, None)
    fc = pd.DataFrame({"timestamp": idx, "yhat": yhat, "y_real": y_real})
    ctx_idx = pd.date_range(end - pd.Timedelta(hours=72), periods=72, freq="h")
    ch = ctx_idx.hour.values
    ctx = pd.Series(np.clip(12 + 8 * np.sin((ch - 7) / 24 * 2 * np.pi)
                            + np.random.normal(0, 2, 72), 2, None), index=ctx_idx)
    return {"source": "synthetic", "forecast": fc, "context": ctx,
            "cut": end - pd.Timedelta(hours=1), "metrics": _metrics(fc["y_real"], fc["yhat"])}


@st.cache_data(show_spinner=False)
def load_history() -> pd.DataFrame:
    """Histórico 2013–2019 para a página Histórico; sintetiza se faltar o CSV."""
    if HIST_CSV.exists():
        df = pd.read_csv(HIST_CSV)
        for c in ["datetime", "date", "time", "ds", df.columns[0]]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")
                df = df.dropna(subset=[c]).set_index(c).sort_index()
                break
        for cand in TARGET_CANDIDATES:
            if cand in df.columns:
                df = df.rename(columns={cand: "PM2.5"})
                break
        return df
    return _synthetic_history()


def _synthetic_history() -> pd.DataFrame:
    rng = pd.date_range("2016-01-01", "2019-12-31 23:00", freq="h")
    n = len(rng); hour = rng.hour.values; doy = rng.dayofyear.values
    diurnal = 8 * np.sin((hour - 7) / 24 * 2 * np.pi) + 6 * np.sin((hour - 19) / 12 * 2 * np.pi)
    seasonal = 14 * np.cos((doy - 200) / 365 * 2 * np.pi)
    pm25 = np.clip(26 + diurnal + seasonal + np.random.normal(0, 4, n), 3, None)
    df = pd.DataFrame({"PM2.5": pm25}, index=rng); df.index.name = "datetime"
    return df


def latest_reading(forecast_bundle: dict) -> dict:
    """Leitura 'atual' = último observado antes do corte (ou início do contexto)."""
    ctx = forecast_bundle["context"]
    last_obs = float(ctx.iloc[-1]) if len(ctx) else float(forecast_bundle["forecast"]["yhat"].iloc[0])
    ts = ctx.index[-1] if len(ctx) else forecast_bundle["cut"]
    return {"timestamp": ts, "pm25": last_obs}


def stations() -> pd.DataFrame:
    """Estações da RMSP para o mapa (Congonhas em destaque — é a do modelo)."""
    rows = [
        ("Congonhas",   -23.626, -46.656, 12),   # estação do modelo operacional
        ("Pinheiros",   -23.561, -46.702, 14),
        ("Santana",     -23.503, -46.628, 10),
        ("Lapa",        -23.522, -46.705, 11),
        ("Tatuapé",     -23.540, -46.576, 13),
        ("Moema",       -23.601, -46.663, 16),
        ("Parelheiros", -23.827, -46.728, 9),
        ("Guarulhos",   -23.454, -46.533, 13),
    ]
    return pd.DataFrame(rows, columns=["estacao", "lat", "lon", "pm25"])
