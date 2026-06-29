"""
app.py  —  Respira SP / AirSP Intelligence  (Visão Geral)
"""

import os
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from styling import (inject_css, render_gauge, PALETTE,
                     classify_iqar, pm25_to_iqar, IQAR_BANDS)

# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
API_URL = os.getenv("RESPIRA_API_URL", "http://localhost:8000")
STATION = "Congonhas"

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_forecast() -> dict | None:
    try:
        resp = requests.get(f"{API_URL}/forecast", timeout=10)
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

def stations() -> pd.DataFrame:
    rows = [
        ("Congonhas",   -23.626, -46.656, 12),
        ("Pinheiros",   -23.561, -46.702, 14),
        ("Santana",     -23.503, -46.628, 10),
        ("Lapa",        -23.522, -46.705, 11),
        ("Tatuapé",     -23.540, -46.576, 13),
        ("Moema",       -23.601, -46.663, 16),
        ("Parelheiros", -23.827, -46.728,  9),
        ("Guarulhos",   -23.454, -46.533, 13),
    ]
    return pd.DataFrame(rows, columns=["estacao", "lat", "lon", "pm25"])

def station_map(df: pd.DataFrame) -> go.Figure:
    colors = [classify_iqar(pm25_to_iqar(v))[1] for v in df["pm25"]]
    fig = go.Figure(go.Scattermap(
        lat=df["lat"], lon=df["lon"], mode="markers+text",
        marker=dict(size=24, color=colors, opacity=0.92),
        text=df["pm25"].astype(int).astype(str),
        textfont=dict(color="#0B1220", size=11, family="Inter"),
        customdata=df["estacao"],
        hovertemplate="<b>%{customdata}</b><br>PM2.5: %{text} µg/m³<extra></extra>"))
    fig.update_layout(
        map=dict(style="open-street-map", center=dict(lat=-23.59, lon=-46.65), zoom=9.3),
        margin=dict(l=0, r=0, t=0, b=0), height=320, paper_bgcolor="rgba(0,0,0,0)")
    return fig

def forecast_chart(records: list) -> go.Figure:
    timestamps = [r["timestamp_utc"]  for r in records]
    values     = [r["pm25_forecast"]  for r in records]
    colors     = [classify_iqar(pm25_to_iqar(v))[1] for v in values]
    fig = go.Figure(go.Scatter(
        x=timestamps, y=values, mode="lines+markers",
        line=dict(color="#34D399", width=2.5, shape="spline"),
        marker=dict(size=9, color=colors, line=dict(width=2, color=PALETTE["panel"])),
        hovertemplate="%{x|%d/%m %H:%M}<br><b>%{y:.1f}</b> µg/m³<extra></extra>"))
    fig.update_layout(
        height=260, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PALETTE["muted"], family="Inter", size=12),
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.06)",
                   zeroline=False, title="PM2.5 (µg/m³)"))
    return fig

def pollutant_bars(values: dict) -> go.Figure:
    names = list(values.keys())[::-1]
    vals  = [values[n][0] for n in names]
    units = [values[n][1] for n in names]
    ceil  = {"PM2.5": 75, "PM10": 150, "O3": 160, "NO2": 200, "CO": 9}
    colors = []
    for n, v in zip(names, vals):
        frac = min(v / ceil.get(n, 100), 1)
        colors.append("#4CAF50" if frac < .4 else "#FBC02D" if frac < .7 else "#FB8C00")
    fig = go.Figure(go.Bar(
        x=vals, y=names, orientation="h", marker=dict(color=colors), width=0.55,
        text=[f"{v:g} {u}" for v, u in zip(vals, units)], textposition="outside",
        textfont=dict(color=PALETTE["text"], size=12), hoverinfo="skip"))
    lay = dict(height=210, margin=dict(l=8, r=8, t=8, b=8),
               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
               font=dict(color=PALETTE["muted"], family="Inter", size=12),
               showlegend=False)
    fig.update_layout(**lay)
    fig.update_xaxes(visible=False, range=[0, max(vals) * 1.35])
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig

# --------------------------------------------------------------------------- #
# APP
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="Respira SP · AirSP Intelligence",
                   page_icon="🌫️", layout="wide")
inject_css()

data    = fetch_forecast() or synthetic_forecast()
is_live = fetch_forecast() is not None

records    = data["forecast_24h"]
pm25_atual = data["pm25_current"] or records[0]["pm25_forecast"]
last_ts    = pd.to_datetime(data["last_updated_utc"], utc=True)
iqar_now   = pm25_to_iqar(pm25_atual)
label_now, color_now = classify_iqar(iqar_now)

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
            f'{last_ts:%d/%m/%Y %H:%M} UTC</p>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="card-title">Mapa da Qualidade do Ar (RMSP)</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(station_map(stations()), width="stretch",
                        config={"displayModeBar": False}, key="mapa_rmsp_home")

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

    with st.container(border=True):
        st.markdown('<div class="card-title">Principais Poluentes (Atual)</div>',
                    unsafe_allow_html=True)
        poll = {"PM2.5": (round(pm25_atual), "µg/m³"), "PM10": (88, "µg/m³"),
                "O3": (28, "µg/m³"), "NO2": (18, "µg/m³"), "CO": (0.6, "ppm")}
        st.plotly_chart(pollutant_bars(poll), width="stretch",
                        config={"displayModeBar": False})

with col_chat:
    with st.container(border=True):
        st.markdown('<div class="card-title">✨ Assistente Inteligente</div>', unsafe_allow_html=True)
        if "chat" not in st.session_state:
            st.session_state.chat = [
                ("bot", f"A qualidade do ar agora está **{label_now}** "
                        f"(IQAr {iqar_now:.0f}) na estação {STATION}."),
            ]
        bubbles = "".join(f"<div class='bubble {who}'>{txt}</div>"
                          for who, txt in st.session_state.chat)
        st.markdown(f"<div class='chat-wrap'>{bubbles}</div>", unsafe_allow_html=True)
        q = st.chat_input("Digite sua pergunta…")
        if q:
            st.session_state.chat.append(("user", q))
            st.session_state.chat.append(("bot", f"PM2.5 atual: {pm25_atual:.1f} µg/m³ — {label_now}."))
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
