import streamlit as st

dashboard = st.Page(
    "views/dashboard.py",
    title="Dashboard",
    icon="🏠",
    default=True,
)

avaliacao = st.Page(
    "pages/1_Avaliação.py",
    title="Avaliação",
    icon="📈",
)

mapa = st.Page(
    "pages/2_Mapa.py",
    title="Mapa",
    icon="🗺️",
)

historico = st.Page(
    "pages/3_Histórico.py",
    title="Histórico",
    icon="📊",
)

sobre = st.Page(
    "pages/4_Sobre.py",
    title="Sobre",
    icon="ℹ️",
)

navigation = st.navigation(
    [
        dashboard,
        avaliacao,
        mapa,
        historico,
        sobre,
    ]
)

navigation.run()
