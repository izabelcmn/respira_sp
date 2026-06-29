"""pages/2_Mapa.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from styling import inject_css, IQAR_BANDS
from app import stations, station_map

st.set_page_config(page_title="Mapa · Respira SP", page_icon="🗺️", layout="wide")
inject_css()

st.markdown("## 🗺️ Mapa da Qualidade do Ar — RMSP")

with st.container(border=True):
    st.plotly_chart(station_map(stations()), width="stretch",
                    config={"displayModeBar": False}, key="mapa_rmsp")
    legend = " &nbsp;&nbsp; ".join(
        f"<span class='pill' style='background:{c}22;color:{c}'>● {lbl}</span>"
        for _, lbl, c in IQAR_BANDS)
    st.markdown(legend, unsafe_allow_html=True)

st.markdown('<p class="muted">Marcadores mostram o PM2.5 por estação.</p>',
            unsafe_allow_html=True)
