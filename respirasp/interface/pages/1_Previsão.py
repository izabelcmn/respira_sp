"""pages/1_Previsão.py — Avaliação e previsão de PM2.5
(exibido como "Avaliação do modelo" na sidebar via CSS — arquivo NÃO renomeado)"""

import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from styling import inject_css, kpi_card, classify_iqar, pm25_to_iqar, PALETTE

API_URL = os.getenv("RESPIRA_API_URL", "http://localhost:8501")
STATION  = "Congonhas"

# ── Splits do dataset ─────────────────────────────────────────────────────────
DATASET = {
    "Treino": {"shape": "16 104 × 7", "inicio": "2016-03-01", "fim": "2017-12-31"},
    "Val."  : {"shape": " 8 760 × 7", "inicio": "2018-01-01", "fim": "2018-12-31"},
    "Teste" : {"shape": " 5 499 × 7", "inicio": "2019-01-01", "fim": "2019-08-18"},
}

# ── Resultados walk-forward — conjunto de teste 2019 ─────────────────────────
BACKTEST = [
    {"Modelo": "LightGBM", "MAE":  4.71, "RMSE":  6.03, "Rank": 1,
     "Observação": "Melhor modelo — menor MAE e RMSE no conjunto de teste."},
    {"Modelo": "XGBoost",  "MAE":  4.80, "RMSE":  6.14, "Rank": 2,
     "Observação": "Muito próximo do LightGBM; segundo melhor geral."},
    {"Modelo": "SARIMAX",  "MAE":  7.31, "RMSE":  9.49, "Rank": 3,
     "Observação": "Linha de base estatística; supera LSTM em RMSE."},
    {"Modelo": "LSTM",     "MAE":  7.87, "RMSE":  9.55, "Rank": 4,
     "Observação": "Alta variabilidade entre janelas; pior MAE médio."},
]
BEST = BACKTEST[0]

# ── Fetch forecast ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def fetch_forecast() -> dict | None:
    try:
        resp = requests.get(f"{API_URL}/forecast", timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None

def forecast_chart(records: list) -> go.Figure:
    timestamps = [r.get("timestamp_sp", r["timestamp_utc"]) for r in records]
    values     = [r["pm25_forecast"] for r in records]
    fig = go.Figure(go.Scatter(
        x=timestamps, y=values, mode="lines+markers",
        line=dict(color="#34D399", width=2.4, dash="dash"),
        marker=dict(size=6, color="#34D399"),
        hovertemplate="%{x|%d/%m %H:%M}<br>prev %{y:.1f} µg/m³<extra></extra>"))
    fig.update_layout(
        height=340, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PALETTE["muted"], family="Inter", size=12),
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.06)",
                   zeroline=False, title="PM2.5 (µg/m³)"))
    return fig

# ── Layout ────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Previsão · Respira SP", layout="wide",
                   initial_sidebar_state="expanded")
inject_css()

st.markdown("## Avaliação dos modelos e Previsão de PM2.5 (24h)")
st.markdown(
    f'<p class="muted">Estação {STATION} · Walk-forward validation · '
    f'Horizonte de 24h direto (sem autorregressão)</p>',
    unsafe_allow_html=True)

# ── O que é PM2.5? (contexto) ─────────────────────────────────────────────────
with st.container(border=True):
    st.markdown('<div class="card-title">O que é PM2.5?</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="muted">'
        'PM2.5 vem do inglês <i>Particulate Matter</i> '
        '(MP — Material Particulado, em português) e corresponde a partículas '
        'finas com diâmetro ≤ 2,5 µm — cerca de 30× mais finas que um fio de cabelo. '
        'Por serem minúsculas, podem penetrar profundamente nos pulmões e alcançar '
        'a corrente sanguínea, estando associadas a impactos nos sistemas '
        'respiratório e cardiovascular. É o poluente que este modelo prevê '
        'para as próximas 24h.'
        '</p>',
        unsafe_allow_html=True,
    )

st.divider()

# ── 1. Dataset ────────────────────────────────────────────────────────────────
with st.expander("Partição do dataset", expanded=False):
    st.markdown(
        "Divisão temporal rígida — sem sobreposição entre conjuntos. "
        "Scalers ajustados **apenas** no treino para evitar vazamento de dados.")
    cols = st.columns(3)
    for col, (nome, info) in zip(cols, DATASET.items()):
        col.markdown(
            kpi_card(info["shape"], nome,
                     f"{info['inicio']} → {info['fim']}"),
            unsafe_allow_html=True)

st.divider()

# ── 2. Comparação de modelos ──────────────────────────────────────────────────
st.markdown("### Comparação — walk-forward backtest (teste 2019)")
st.markdown(
    '<p class="muted">Métricas médias sobre todas as janelas semanais de 24h '
    '(jan–ago 2019). Avaliação independente: cada janela treina no passado e '
    'prediz o futuro imediato.</p>',
    unsafe_allow_html=True)

# KPIs do melhor modelo
c1, c2, c3, c4 = st.columns(4)
c1.markdown(kpi_card("LightGBM", "Melhor modelo", "menor MAE e RMSE"),
            unsafe_allow_html=True)
c2.markdown(kpi_card(f"{BEST['MAE']:.2f}", "MAE médio (µg/m³)",
                     f"vs XGBoost {BACKTEST[1]['MAE']:.2f}"),
            unsafe_allow_html=True)
c3.markdown(kpi_card(f"{BEST['RMSE']:.2f}", "RMSE médio (µg/m³)",
                     f"vs XGBoost {BACKTEST[1]['RMSE']:.2f}"),
            unsafe_allow_html=True)
c4.markdown(kpi_card("↓ 38%", "MAE vs LSTM",
                     "LightGBM 4.71 vs LSTM 7.87"),
            unsafe_allow_html=True)

st.write("")

# Tabela completa
df = pd.DataFrame(BACKTEST).sort_values("MAE")
st.dataframe(
    df[["Rank", "Modelo", "MAE", "RMSE", "Observação"]],
    hide_index=True,
    use_container_width=True,
    column_config={
        "MAE":  st.column_config.ProgressColumn(
            "MAE (µg/m³)", format="%.2f", min_value=0.0, max_value=10.0),
        "RMSE": st.column_config.ProgressColumn(
            "RMSE (µg/m³)", format="%.2f", min_value=0.0, max_value=12.0),
    })

st.info(
    "**Leitura:** LightGBM e XGBoost dominam com MAE ~4.7–4.8 µg/m³, "
    "cerca de **38% inferior** ao LSTM (7.87) e SARIMAX (7.31). "
    "A diferença entre LightGBM e XGBoost (0.09 µg/m³ em MAE) é marginal — "
    "o LightGBM foi escolhido como modelo operacional por consistência ao longo "
    "das janelas de teste e menor RMSE médio.")

st.divider()

# ── 3. Previsão operacional ───────────────────────────────────────────────────
st.markdown("### Previsão operacional — LightGBM (24h à frente)")
st.markdown(
    '<p class="muted">Modelo treinado em Congonhas (2016–2017), '
    'aplicado a dados meteorológicos recentes via Open-Meteo API.</p>',
    unsafe_allow_html=True)

data    = fetch_forecast()
is_live = data is not None

if not is_live:
    st.info("Modo demo: API indisponível. O gráfico de previsão requer a API ativa.")

with st.container(border=True):
    st.markdown('<div class="card-title">Previsão de PM2.5 — próximas 24h</div>',
                unsafe_allow_html=True)
    if is_live:
        st.plotly_chart(forecast_chart(data["forecast_24h"]),
                        use_container_width=True,
                        config={"displayModeBar": False})
        peak = max(r["pm25_forecast"] for r in data["forecast_24h"])
        cat, color = classify_iqar(pm25_to_iqar(peak))
        st.markdown(
            f'<p class="muted">Pico previsto: <b>{peak:.1f} µg/m³</b> '
            f'— categoria <span style="color:{color}">{cat}</span></p>',
            unsafe_allow_html=True)
    else:
        st.warning("Inicie a API com `uvicorn respirasp.api.fast:app --port 8501` "
           "para ver a previsão ao vivo.")
