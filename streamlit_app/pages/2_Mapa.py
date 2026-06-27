"""pages/2_Mapa.py — mapa da RMSP com estações coloridas por IQAr."""
import streamlit as st
from utils.styling import inject_css, IQAR_BANDS
from utils.data import stations
from utils.charts import station_map

st.set_page_config(page_title="Mapa · Respira SP", page_icon="🗺️", layout="wide")
inject_css()

st.markdown("## 🗺️ Mapa da Qualidade do Ar — RMSP")

with st.container(border=True):
    st.plotly_chart(station_map(stations()), width="stretch",
                    config={"displayModeBar": False})
    legend = " &nbsp;&nbsp; ".join(
        f"<span class='pill' style='background:{c}22;color:{c}'>● {lbl}</span>"
        for _, lbl, c in IQAR_BANDS)
    st.markdown(legend, unsafe_allow_html=True)

st.markdown('<p class="muted">Marcadores mostram o PM2.5 por estação. Para dados ao vivo, '
            'conecte CETESB/OpenAQ em utils/data.stations().</p>', unsafe_allow_html=True)
