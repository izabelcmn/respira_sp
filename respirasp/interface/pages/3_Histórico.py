"""pages/3_Histórico.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path
from styling import inject_css, kpi_card, classify_iqar, pm25_to_iqar, PALETTE
from respirasp.params import LOCAL_DATA_PATH

HIST_CSV = Path(LOCAL_DATA_PATH) / \
           "data_interpolacao_gaps_maiores_medias" / \
           "dados_full_features_2016_2019_fill_mean.csv"

st.set_page_config(page_title="Histórico · Respira SP", page_icon="📊", layout="wide")
inject_css()

st.markdown("## 📊 Histórico de PM2.5 (2016–2019)")
st.markdown('<p class="muted">Base de treinamento do LightGBM — Estratégia 3 '
            '(interpolação + imputação sazonal)</p>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_history() -> pd.DataFrame:
    if not HIST_CSV.exists():
        st.warning(f"CSV histórico não encontrado: {HIST_CSV}")
        return pd.DataFrame({"PM2.5": []})

    df = pd.read_csv(HIST_CSV)

    for c in ["time", "datetime", "date", "ds"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
            df = df.dropna(subset=[c]).set_index(c).sort_index()
            break

    for cand in ["MP2.5", "PM2.5", "MP2_5", "mp2.5"]:
        if cand in df.columns:
            df = df.rename(columns={cand: "PM2.5"})
            break

    return df


def history_line(s: pd.Series) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=s.index, y=s.values, mode="lines",
        line=dict(color=PALETTE["brand"], width=1.4),
        hovertemplate="%{x|%d/%m/%Y %H:%M}<br><b>%{y:.0f}</b> µg/m³<extra></extra>"
    ))
    fig.update_layout(
        height=340, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PALETTE["muted"], family="Inter", size=12),
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.06)",
                   zeroline=False, title="PM2.5 (µg/m³)")
    )
    return fig


hist = load_history()
pm   = hist["PM2.5"].dropna() if "PM2.5" in hist.columns else pd.Series(dtype=float)

if pm.empty:
    st.stop()

dmin, dmax = pm.index.min().date(), pm.index.max().date()
c1, c2 = st.columns(2)
start = c1.date_input("Início",
                      value=max(dmin, (pm.index.max() - pd.Timedelta(days=90)).date()),
                      min_value=dmin, max_value=dmax)
end   = c2.date_input("Fim", value=dmax, min_value=dmin, max_value=dmax)

mask = (pm.index.date >= start) & (pm.index.date <= end)
sel  = pm[mask]

if sel.empty:
    st.warning("Sem dados nesse intervalo. Ajuste as datas.")
    st.stop()

k1, k2, k3 = st.columns(3)
mean_v        = sel.mean()
label_mean, _ = classify_iqar(pm25_to_iqar(mean_v))
k1.markdown(kpi_card(f"{mean_v:.0f}", "PM2.5 médio (µg/m³)", label_mean),
            unsafe_allow_html=True)
k2.markdown(kpi_card(f"{sel.max():.0f}", "Máximo (µg/m³)", f"{sel.idxmax():%d/%m/%Y}"),
            unsafe_allow_html=True)
k3.markdown(kpi_card(f"{sel.min():.0f}", "Mínimo (µg/m³)", f"{sel.idxmin():%d/%m/%Y}"),
            unsafe_allow_html=True)

st.write("")
with st.container(border=True):
    st.markdown('<div class="card-title">Série temporal — PM2.5</div>',
                unsafe_allow_html=True)
    st.plotly_chart(history_line(sel), use_container_width=True,
                    config={"displayModeBar": False}, key="historico_line")
