"""pages/4_Sobre.py"""
import streamlit as st
import sys, os, base64
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from styling import inject_css, PALETTE

STATION      = "Congonhas"
TRAIN_PERIOD = "2016–2019"

st.set_page_config(page_title="Sobre · Respira SP", page_icon="ℹ️",
                   layout="wide", initial_sidebar_state="expanded")
inject_css()

# ── Pasta com as fotos da equipe ──────────────────────────────────────────────
# Crie: respirasp/interface/assets/team/  e coloque izabel.jpg, gabriel.jpg, joao.jpg
ASSETS = Path(__file__).resolve().parent.parent / "assets" / "team"

TEAM = [
    {"nome": "Izabel Nogueira",
     "papel": " ",
     "foto": "izabel.jpg",
     "github": "github.com/izabel",
     "linkedin": "linkedin.com/in/izabel"},
    {"nome": "Gabriel Marques",
     "papel": " ",
     "foto": "gabriel.jpg",
     "github": "github.com/gabriel",
     "linkedin": "linkedin.com/in/gabriel"},
    {"nome": "João Pedro Campos Correa de Araújo",
     "papel": " ",
     "foto": "joao.jpg",
     "github": "github.com/JoaoPedroCampos00",
     "linkedin": "linkedin.com/in/joao"},
]


def _img_data_uri(path: Path) -> str | None:
    """Lê a foto e devolve um data-URI base64 (ou None se o arquivo não existir)."""
    if not path.exists():
        return None
    ext  = path.suffix.lstrip(".").lower()
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    b64  = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/{mime};base64,{b64}"


def member_card(m: dict) -> str:
    """Cartão de um membro: foto circular (ou iniciais), nome, papel e links."""
    uri = _img_data_uri(ASSETS / m["foto"])
    if uri:
        avatar = (f'<img src="{uri}" style="width:120px;height:120px;'
                  f'border-radius:50%;object-fit:cover;'
                  f'border:3px solid {PALETTE["border"]};">')
    else:
        # Sem foto ainda → círculo com as iniciais (placeholder).
        iniciais = "".join(p[0] for p in m["nome"].split()[:2]).upper()
        avatar = (f'<div style="width:120px;height:120px;border-radius:50%;'
                  f'background:{PALETTE["panel_2"]};display:flex;'
                  f'align-items:center;justify-content:center;font-size:2rem;'
                  f'font-weight:800;color:{PALETTE["muted"]};'
                  f'border:3px solid {PALETTE["border"]};margin:0 auto;">'
                  f'{iniciais}</div>')
    return f"""
    <div style="text-align:center;">
      {avatar}
      <div style="font-weight:700;color:{PALETTE['text']};margin-top:12px;
                  line-height:1.3;">{m['nome']}</div>
      <div class="muted" style="margin-top:2px;">{m['papel']}</div>
      <div class="muted" style="margin-top:8px;font-size:.72rem;line-height:1.6;">
        {m['github']}<br>{m['linkedin']}
      </div>
    </div>
    """


st.markdown("## ℹ️ Sobre o Respira SP")
st.markdown(f"""
O **Respira SP** prevê **PM2.5** **24 horas à frente** em São Paulo. O modelo
operacional é um **LightGBM (GBDT)** treinado na estação **{STATION}** ({TRAIN_PERIOD}),
servido aqui sobre dados reais recentes.
""")

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True):
        st.markdown('<div class="card-title">Dados & Features</div>', unsafe_allow_html=True)
        st.markdown("""
- **Alvo:** PM2.5 (`MP2.5`)
- **46 features:** meteorologia + lags + cíclicas (hora/dia/mês) + `is_winter`
- **Fonte da verdade das features:** `lightgbm_features.pkl` (ordem importa)
- **Ingestão:** OpenAQ (PM2.5) + OpenMeteo (meteo), em UTC
""")
with col2:
    with st.container(border=True):
        st.markdown('<div class="card-title">Avaliação</div>', unsafe_allow_html=True)
        st.markdown("""
- **Operacional:** janela de 24h sobre dados reais recentes
- **Métricas:** MAE, RMSE, R², MBE, NMAE
- **Backtest 2019:** walk-forward (stride 24h) p/ comparar modelos
- **Previsão direta** de 24h evita acúmulo de erro autorregressivo
""")

st.divider()

# ── Equipe ────────────────────────────────────────────────────────────────────
st.markdown("### Nossa equipe")
st.markdown('<p class="muted">Le Wagon · Bootcamp MLOps · Batch 2209</p>',
            unsafe_allow_html=True)
st.write("")

cols = st.columns(3)
for col, m in zip(cols, TEAM):
    col.markdown(member_card(m), unsafe_allow_html=True)

st.write("")
st.caption("Respira SP · interface: respirasp/interface/")
