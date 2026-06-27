"""pages/4_Sobre.py — descrição do projeto e metodologia (para a banca)."""
import streamlit as st
from utils.styling import inject_css
from utils.data import STATION, TRAIN_PERIOD

st.set_page_config(page_title="Sobre · Respira SP", page_icon="ℹ️", layout="wide")
inject_css()

st.markdown("## ℹ️ Sobre o Respira SP")
st.markdown(
    f"""
O **Respira SP** prevê **PM2.5** **24 horas à frente** em São Paulo. O modelo
operacional é um **LightGBM (GBDT)** treinado na estação **{STATION}** ({TRAIN_PERIOD}),
servido aqui sobre dados reais recentes. Esta interface apenas **consome** os
artefatos gerados pelo pipeline do grupo (`.pkl` + CSV operacional) — não treina nada.
""")

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.markdown('<div class="card-title">Dados & Features</div>', unsafe_allow_html=True)
        st.markdown(
            """
- **Alvo:** PM2.5 (`MP2.5`)
- **46 features:** meteorologia + lags + cíclicas (hora/dia/mês) + `is_winter`
- **Fonte da verdade das features:** `lightgbm_features.pkl` (ordem importa)
- **Ingestão:** OpenAQ (PM2.5) + OpenMeteo (meteo), em UTC
""")
with col2:
    with st.container(border=True):
        st.markdown('<div class="card-title">Avaliação</div>', unsafe_allow_html=True)
        st.markdown(
            """
- **Operacional:** janela de 24h sobre dados reais recentes
- **Métricas:** MAE, RMSE, R², MBE, NMAE (MAPE evitado — valores ~0)
- **Backtest 2019:** walk-forward (stride 24h) p/ comparar modelos
- **Previsão direta** de 24h evita acúmulo de erro autorregressivo
""")

st.caption("Respira SP · github.com/izabelcmn/respira_sp · interface: streamlit_app/")
