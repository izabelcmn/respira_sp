"""pages/3_Histórico.py — explorador da série histórica de PM2.5."""
import pandas as pd
import streamlit as st
from utils.styling import inject_css, kpi_card, classify_iqar, pm25_to_iqar
from utils.data import load_history
from utils.charts import history_line

st.set_page_config(page_title="Histórico · Respira SP", page_icon="📊", layout="wide")
inject_css()

st.markdown("## 📊 Histórico de PM2.5")

hist = load_history()
pm = hist["PM2.5"].dropna()

dmin, dmax = pm.index.min().date(), pm.index.max().date()
c1, c2 = st.columns(2)
start = c1.date_input("Início",
                      value=max(dmin, (pm.index.max() - pd.Timedelta(days=90)).date()),
                      min_value=dmin, max_value=dmax)
end = c2.date_input("Fim", value=dmax, min_value=dmin, max_value=dmax)

mask = (pm.index.date >= start) & (pm.index.date <= end)
sel = pm[mask]
if sel.empty:
    st.warning("Sem dados nesse intervalo. Ajuste as datas."); st.stop()

k1, k2, k3 = st.columns(3)
mean_v = sel.mean()
label_mean, _ = classify_iqar(pm25_to_iqar(mean_v))
k1.markdown(kpi_card(f"{mean_v:.0f}", "PM2.5 médio (µg/m³)", label_mean), unsafe_allow_html=True)
k2.markdown(kpi_card(f"{sel.max():.0f}", "Máximo (µg/m³)", f"{sel.idxmax():%d/%m/%Y}"), unsafe_allow_html=True)
k3.markdown(kpi_card(f"{sel.min():.0f}", "Mínimo (µg/m³)", f"{sel.idxmin():%d/%m/%Y}"), unsafe_allow_html=True)

st.write("")
with st.container(border=True):
    st.markdown('<div class="card-title">Série temporal — PM2.5</div>', unsafe_allow_html=True)
    st.plotly_chart(history_line(sel), width="stretch", config={"displayModeBar": False})
