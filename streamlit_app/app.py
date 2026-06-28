"""
app.py  —  Respira SP / AirSP Intelligence  (Visão Geral)
=========================================================
Painel principal. Lê os artefatos do grupo (LightGBM .pkl + CSV operacional) e
mostra: qualidade do ar atual, previsão de 24h (observado×previsto), mapa,
poluentes, assistente e o pipeline no rodapé.

A UI NÃO importa nada do pacote do grupo — só LÊ os artefatos. Acoplamento mínimo.

Rodar (de dentro de respira_sp/streamlit_app):
    streamlit run app.py
"""

import streamlit as st

from utils.styling import (inject_css, render_gauge, PALETTE,
                           classify_iqar, pm25_to_iqar, IQAR_BANDS)
from utils.assistant import answer
from utils.data import lightgbm_forecast, latest_reading, stations, STATION
from utils.charts import obs_vs_pred, pollutant_bars, station_map

st.set_page_config(page_title="Respira SP · AirSP Intelligence",
                   page_icon="🌫️", layout="wide")
inject_css()

# --------------------------------------------------------------------------- #
# Dados: roda o LightGBM ao vivo (ou cai no sintético se faltar .pkl/CSV).
# --------------------------------------------------------------------------- 
bundle = lightgbm_forecast(n=24)
fc = bundle["forecast"]
reading = latest_reading(bundle)
iqar_now = pm25_to_iqar(reading["pm25"])
label_now, color_now = classify_iqar(iqar_now)
is_live = bundle["source"] == "lightgbm"

# Sidebar (marca + status da fonte)
with st.sidebar:
    st.markdown(
        f"<h2 style='margin:0'>🌫️ AirSP <span style='color:{PALETTE['brand']}'>Intelligence</span></h2>"
        f"<p class='muted' style='margin-top:2px'>Respira SP · previsão de PM2.5</p>",
        unsafe_allow_html=True)
    st.divider()
    if is_live:
        st.caption("🟢 LightGBM ativo · dados operacionais")
    else:
        st.caption("🟡 Modo demo (sintético) — copie o .pkl e o CSV operacional "
                   "para o repo para ativar o LightGBM.")

# Layout em 3 colunas (esquerda larga, meio, chat)
col_left, col_mid, col_chat = st.columns([1.05, 1.15, 0.9], gap="medium")

# ----------------------------- COLUNA ESQUERDA ----------------------------- #
with col_left:
    with st.container(border=True):
        st.markdown('<div class="card-title">Qualidade do Ar Atual</div>', unsafe_allow_html=True)
        st.markdown(f'<p class="muted">Estação: {STATION}, São Paulo · SP</p>', unsafe_allow_html=True)
        st.markdown(render_gauge(iqar_now), unsafe_allow_html=True)
        st.markdown(
            f'<p class="muted" style="margin-top:10px">Última leitura: '
            f'{reading["timestamp"]:%d/%m/%Y %H:%M} UTC</p>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="card-title">Mapa da Qualidade do Ar (RMSP)</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(station_map(stations()), width="stretch",
                        config={"displayModeBar": False})

# ------------------------------ COLUNA MEIO -------------------------------- #
with col_mid:
    with st.container(border=True):
        st.markdown('<div class="card-title">Previsão 24h — PM2.5 (µg/m³) · LightGBM</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(obs_vs_pred(bundle["context"], fc, bundle["cut"]),
                        width="stretch", config={"displayModeBar": False})
        legend = " &nbsp; ".join(
            f"<span class='pill' style='background:{c}22;color:{c}'>● {lbl}</span>"
            for _, lbl, c in IQAR_BANDS[:4])
        st.markdown(legend, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="card-title">Principais Poluentes (Atual)</div>',
                    unsafe_allow_html=True)
        # Só PM2.5 é real (vem da leitura). Os demais são ilustrativos — troque por
        # fonte real (CETESB/OpenAQ) quando integrar.
        poll = {"PM2.5": (round(reading["pm25"]), "µg/m³"), "PM10": (88, "µg/m³"),
                "O3": (28, "µg/m³"), "NO2": (18, "µg/m³"), "CO": (0.6, "ppm")}
        st.plotly_chart(pollutant_bars(poll), width="stretch",
                        config={"displayModeBar": False})

# ------------------------------ COLUNA CHAT -------------------------------- #
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
            st.session_state.chat.append(("bot", answer(q, reading, iqar_now, label_now)))
            st.rerun()

# RODAPÉ — pipeline de dados (HTML autocontido: renderiza ok num único markdown)
st.markdown(
    """
    <div class="pipe">
      <div class="pipe-step"><h4>🗄️ Dados Históricos</h4><p>CETESB + OpenAQ (2016–2019)</p></div>
      <div class="pipe-arrow">→</div>
      <div class="pipe-step"><h4>📡 Dados Operacionais</h4><p>OpenAQ + OpenMeteo (tempo real)</p></div>
      <div class="pipe-arrow">→</div>
      <div class="pipe-step"><h4>🧠 LightGBM</h4><p>Previsão de PM2.5 24h à frente</p></div>
      <div class="pipe-arrow">→</div>
      <div class="pipe-step"><h4>💬 IA Conversacional</h4><p>Respostas em linguagem natural</p></div>
    </div>
    """, unsafe_allow_html=True)
