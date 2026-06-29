"""pages/1_Previsão.py"""

import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from styling import inject_css, kpi_card, classify_iqar, pm25_to_iqar, PALETTE

API_URL      = os.getenv("RESPIRA_API_URL", "http://localhost:8000")
STATION      = "Congonhas"
TRAIN_PERIOD = "2016–2019"

LGBM_OPERATIONAL = {
    "mae": 6.725, "rmse": 8.174, "r2": 0.1706,
    "mbe": 2.474, "nmae": 70.54, "mape": 414.07,
    "mae_val2018": 4.14, "mean_obs": 9.53,
}

BACKTEST_2019 = {
    "XGBoost":          {"r2": 0.452, "note": "Melhor R² no backtest 2019."},
    "N-HiTS (refit)":   {"r2": 0.390, "note": "Só covariáveis passadas → viés diurno."},
    "LSTM 5.9K":        {"r2": 0.386, "note": "Baseline enxuto."},
    "LSTM 53K (tuned)": {"r2": 0.385, "note": "Mais capacidade, ganho marginal."},
    "N-HiTS (1ª run)":  {"r2": 0.373, "note": "Antes do refit."},
    "SARIMAX":          {"r2": 0.340, "note": "Linha de base estatística."},
}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_forecast() -> dict | None:
    try:
        resp = requests.get(f"{API_URL}/forecast", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None

def forecast_chart(records: list) -> go.Figure:
    timestamps = [r["timestamp_utc"]  for r in records]
    values     = [r["pm25_forecast"]  for r in records]
    fig = go.Figure(go.Scatter(
        x=timestamps, y=values, mode="lines+markers",
        line=dict(color="#34D399", width=2.4, dash="dash"),
        marker=dict(size=6, color="#34D399"),
        hovertemplate="%{x|%d/%m %H:%M}<br>prev %{y:.1f}<extra></extra>"))
    fig.update_layout(
        height=360, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PALETTE["muted"], family="Inter", size=12),
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.06)",
                   zeroline=False, title="PM2.5 (µg/m³)"))
    return fig

st.set_page_config(page_title="Previsão · Respira SP", page_icon="📈", layout="wide")
inject_css()

st.markdown("## 📈 Previsão de PM2.5 (24h) — LightGBM operacional")
st.markdown(f'<p class="muted">Modelo treinado em {STATION} ({TRAIN_PERIOD}), aplicado '
            f'a dados reais recentes. Previsão direta de 24h (sem autorregressão).</p>',
            unsafe_allow_html=True)

data    = fetch_forecast()
is_live = data is not None
m       = LGBM_OPERATIONAL

if not is_live:
    st.info("Modo demo: API indisponível. Métricas exibidas são do backtest.", icon="🟡")

c1, c2, c3 = st.columns(3)
c1.markdown(kpi_card(f"{m['mae']:.2f}", "MAE (µg/m³)",
                     f"validação 2018: {m['mae_val2018']:.2f}"), unsafe_allow_html=True)
c2.markdown(kpi_card(f"{m['rmse']:.2f}", "RMSE (µg/m³)"), unsafe_allow_html=True)
c3.markdown(kpi_card(f"{m['r2']:.3f}", "R²", "janela única / ar limpo"), unsafe_allow_html=True)
c4, c5, c6 = st.columns(3)
mbe = m["mbe"]
c4.markdown(kpi_card(f"{mbe:+.2f}", "MBE (µg/m³)",
                     "superestima" if mbe > 0 else "subestima"), unsafe_allow_html=True)
c5.markdown(kpi_card(f"{m['nmae']:.1f}%", "NMAE", "MAE / média observada"), unsafe_allow_html=True)
c6.markdown(kpi_card(f"{m['mape']:.0f}%", "MAPE", "inflado por valores ~0 → não use"),
            unsafe_allow_html=True)

st.write("")

with st.container(border=True):
    st.markdown('<div class="card-title">Previsão 24h</div>', unsafe_allow_html=True)
    if is_live:
        st.plotly_chart(forecast_chart(data["forecast_24h"]),
                        width="stretch", config={"displayModeBar": False})
    else:
        st.info("API indisponível — gráfico indisponível.")

st.info(
    f"**Leitura para a banca:** o modelo treinado em {TRAIN_PERIOD} mantém o erro "
    f"absoluto controlado mesmo ~7 anos depois (MAE {m['mae_val2018']:.2f} → "
    f"{m['mae']:.2f} µg/m³). O R² baixo e o MAPE altíssimo vêm de uma "
    f"janela de **ar limpo** (média ≈ {m['mean_obs']:.1f} µg/m³): pouca "
    f"variância para explicar e divisões por valores próximos de zero — não indicam falha do modelo.",
    icon="🎓")

st.markdown("### Backtest histórico (walk-forward, 2019)")
st.markdown('<p class="muted">Regime de avaliação diferente do operacional acima — '
            'NÃO compare os R² diretamente.</p>', unsafe_allow_html=True)

rows = [{"Modelo": k, "R² (2019)": v["r2"], "Observação": v["note"]}
        for k, v in BACKTEST_2019.items()]
df = pd.DataFrame(rows).sort_values("R² (2019)", ascending=False)
st.dataframe(df, width="stretch", hide_index=True,
             column_config={"R² (2019)": st.column_config.ProgressColumn(
                 "R² (2019)", format="%.3f", min_value=0.0, max_value=0.5)})
