"""pages/3_Histórico.py"""
import streamlit as st
from styling import inject_css

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(page_title="Histórico · Respira SP", page_icon="📊", layout="wide")
inject_css()

st.markdown("## 📊 Histórico de PM2.5")
st.info("Dados históricos (2016–2019) disponíveis nos notebooks do projeto. "
        "Esta página será integrada em versões futuras.", icon="📊")
