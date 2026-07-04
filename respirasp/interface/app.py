"""
app.py  —  Respira SP / AirSP Intelligence  (Visão Geral)
"""

import os
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from utils.assistant import answer
from utils.map import stations, station_map

from styling import (inject_css, render_gauge, PALETTE,
                     classify_iqar, pm25_to_iqar, IQAR_BANDS)


# API

API_URL = os.getenv("RESPIRA_API_URL", "http://localhost:8501")
STATION = "Congonhas"

@st.cache_data(ttl=300, show_spinner=False)
def fetch_forecast() -> dict | None:
    try:
        resp = requests.get(f"{API_URL}/forecast", timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"API indisponível ({e}). Exibindo dados sintéticos.")
        return None

def synthetic_forecast() -> dict:
    end  = pd.Timestamp.utcnow().floor("h")
    idx  = pd.date_range(end, periods=24, freq="h")
    h    = idx.hour.values
    yhat = np.clip(12 + 8 * np.sin((h - 7) / 24 * 2 * np.pi)
                      + 6 * np.sin((h - 19) / 12 * 2 * np.pi)
                      + np.random.normal(0, 2, 24), 2, None)
    return {
        "last_updated_utc": str(end),
        "pm25_current":     float(yhat[0]),
        "forecast_24h": [
            {"timestamp_utc": str(ts), "pm25_forecast": round(float(v), 2)}
            for ts, v in zip(idx, yhat)
        ],
        "pm25_max_24h": round(float(yhat.max()), 2),
        "pm25_min_24h": round(float(yhat.min()), 2),
    }

def forecast_chart(records: list) -> go.Figure:
    timestamps = [r.get("timestamp_sp", r["timestamp_utc"]) for r in records]
    values     = [r["pm25_forecast"] for r in records]
    colors     = [classify_iqar(pm25_to_iqar(v))[1] for v in values]

    fig = go.Figure(go.Scatter(
        x=timestamps, y=values, mode="lines+markers",
        line=dict(color="#34D399", width=2.5, shape="spline"),
        marker=dict(size=9, color=colors, line=dict(width=2, color=PALETTE["panel"])),
        hovertemplate="%{x|%d/%m %H:%M}<br><b>%{y:.1f}</b> µg/m³<extra></extra>"
    ))

    fig.update_layout(
        height=260, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PALETTE["muted"], family="Inter", size=12),
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,.06)",
            zeroline=False,
            title="PM2.5 (µg/m³)"
        )
    )
    return fig


# APP
st.set_page_config(page_title="Respira SP · AirSP Intelligence",
                   page_icon="🌫️", layout="wide")
inject_css()

api_data = fetch_forecast()
data = api_data or synthetic_forecast()
is_live = api_data is not None

records = data["forecast_24h"]
pm25_atual = data["pm25_current"] or records[0]["pm25_forecast"]
last_ts = pd.to_datetime(
    data.get("last_updated_sp", data["last_updated_utc"]),
    utc=True
).tz_convert("America/Sao_Paulo")
iqar_now = pm25_to_iqar(pm25_atual)
label_now, color_now = classify_iqar(iqar_now)


# prepare chatbot

forecast_df = pd.DataFrame(records)
forecast_df["timestamp_utc"] = pd.to_datetime(forecast_df["timestamp_utc"], utc=True)
forecast_df = (
    forecast_df
    .rename(columns={"pm25_forecast": "pm25_previsto"})
    .set_index("timestamp_utc")
)
reading = {"pm25": pm25_atual, "timestamp": last_ts}

with st.sidebar:
    st.markdown(
        f"<h2 style='margin:0'>🌫️ AirSP <span style='color:{PALETTE['brand']}'>Intelligence</span></h2>"
        f"<p class='muted' style='margin-top:2px'>Respira SP · previsão de PM2.5</p>",
        unsafe_allow_html=True)
    st.divider()
    if is_live:
        st.caption("🟢 LightGBM ativo · dados operacionais")
    else:
        st.caption("🟡 Modo demo (sintético)")

col_left, col_mid, col_chat = st.columns([1.05, 1.15, 0.9], gap="medium")

with col_left:
    with st.container(border=True):
        st.markdown('<div class="card-title">Qualidade do Ar Atual</div>', unsafe_allow_html=True)
        st.markdown(f'<p class="muted">Estação: {STATION}, São Paulo · SP</p>', unsafe_allow_html=True)
        st.markdown(render_gauge(iqar_now), unsafe_allow_html=True)
        st.markdown(
            f'<p class="muted" style="margin-top:10px">Última leitura: '
            f'{last_ts:%d/%m/%Y %H:%M} São Paulo</p>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="card-title">Mapa — Estação Congonhas</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(
    station_map(stations()),
    width="stretch",
    config={"displayModeBar": False},
    key="mapa_rmsp_home"
)

with col_mid:
    with st.container(border=True):
        st.markdown('<div class="card-title">Previsão 24h — PM2.5 (µg/m³) · LightGBM</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(forecast_chart(records), width="stretch",
                        config={"displayModeBar": False})
        legend = " &nbsp; ".join(
            f"<span class='pill' style='background:{c}22;color:{c}'>● {lbl}</span>"
            for _, lbl, c in IQAR_BANDS[:4])
        st.markdown(legend, unsafe_allow_html=True)

    # Meteorological covariates (model features)
    with st.container(border=True):
        st.markdown('<div class="card-title">Condições Meteorológicas — Congonhas</div>',
                    unsafe_allow_html=True)
        st.markdown(
            '<p class="muted">Covariáveis usadas pelo LightGBM na previsão.</p>',
            unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        m1.metric("Temperatura", "22.4 °C")
        m2.metric("Umidade Relativa", "68 %")
        m3, m4 = st.columns(2)
        m3.metric("Vel. do Vento", "3.2 m/s")
        m4.metric("Precipitação", "0.0 mm")


#          Chatbot

with col_chat:
    with st.container(border=True):
        st.markdown(
            '<div class="card-title">✨ Assistente Inteligente</div>',
            unsafe_allow_html=True)

        if "chat" not in st.session_state:
            st.session_state.chat = [
                ("bot",
                 f"A qualidade do ar agora está **{label_now}** "
                 f"(IQAr {iqar_now:.0f}) na estação {STATION}."),
            ]

        bubbles = "".join(
            f"<div class='bubble {who}'>{txt}</div>"
            for who, txt in st.session_state.chat)
        st.markdown(f"<div class='chat-wrap'>{bubbles}</div>", unsafe_allow_html=True)

        q = st.chat_input("Digite sua pergunta…")
        if q:
            st.session_state.chat.append(("user", q))
            resposta = answer(
                q=q, reading=reading, iqar=iqar_now,
                label=label_now, forecast_df=forecast_df)
            st.session_state.chat.append(("bot", resposta))
            st.rerun()

st.markdown("""
<div class="pipe">
  <div class="pipe-step"><h4>🗄️ Dados Históricos</h4><p>CETESB + OpenAQ (2016–2019)</p></div>
  <div class="pipe-arrow">→</div>
  <div class="pipe-step"><h4>📡 Dados Operacionais</h4><p>OpenAQ + OpenMeteo (tempo real)</p></div>
  <div class="pipe-arrow">→</div>
  <div class="pipe-step"><h4>🧠 LightGBM</h4><p>Previsão de PM2.5 24h à frente</p></div>
  <div class="pipe-arrow">→</div>
  <div class="pipe-step"><h4>🌐 FastAPI + Streamlit</h4><p>Dashboard em tempo real</p></div>
</div>
""", unsafe_allow_html=True)
