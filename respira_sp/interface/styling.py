"""
utils/styling.py
================
Tudo que é "aparência" mora aqui, separado da lógica de dados e dos gráficos.
Assim você consegue mudar o visual inteiro mexendo só neste arquivo.

Contém:
  - PALETTE / IQAR_BANDS .... tokens de design (cores) num só lugar
  - inject_css() ........... injeta o CSS global (cards, sidebar, chat, tipografia)
  - pm25_to_iqar() ......... converte concentração de PM2.5 (µg/m³) -> IQAr (CETESB)
  - classify_iqar() ........ devolve (rótulo, cor) para um valor de IQAr
  - render_gauge() ......... desenha o anel/gauge SVG do IQAr (o elemento-assinatura)
  - kpi_card() ............. helper para cartõezinhos de número
"""

from __future__ import annotations
import streamlit as st

PALETTE = {
    "bg":        "#0B1220",  # fundo da página
    "panel":     "#16202E",  # fundo dos cards
    "panel_2":   "#1C2738",  # variação (hover / chat bot)
    "border":    "rgba(255,255,255,0.07)",
    "text":      "#E6EDF5",  # texto principal
    "muted":     "#8B97A8",  # texto secundário / legendas
    "brand":     "#3B82F6",  # azul de destaque (nav ativa, balão do usuário)
    "brand_dk":  "#1E3A8A",
}

IQAR_BANDS = [
    (40,  "Boa",        "#4CAF50"),
    (80,  "Moderada",   "#FBC02D"),
    (120, "Ruim",       "#FB8C00"),
    (200, "Muito Ruim", "#E53935"),
    (10**9, "Péssima",  "#8E24AA"),
]


_PM25_CONC = [0, 25, 50, 75, 125, 300]
_PM25_IQAR = [0, 40, 80, 120, 200, 400]


def pm25_to_iqar(conc: float) -> float:
    """
    Converte concentração de PM2.5 (µg/m³, média 24h) em IQAr usando a tabela
    da CETESB e interpolação linear — exatamente o procedimento oficial.
    Mantemos isso correto porque a banca pode perguntar de onde sai o "62".
    """
    if conc <= 0:
        return 0.0
    # Procura em qual faixa a concentração cai e interpola.
    for i in range(len(_PM25_CONC) - 1):
        c_lo, c_hi = _PM25_CONC[i], _PM25_CONC[i + 1]
        if c_lo <= conc <= c_hi:
            i_lo, i_hi = _PM25_IQAR[i], _PM25_IQAR[i + 1]
            return i_lo + (i_hi - i_lo) * (conc - c_lo) / (c_hi - c_lo)
    # Acima do último ponto: estende a última inclinação (caso extremo).
    return _PM25_IQAR[-1]


def classify_iqar(iqar: float) -> tuple[str, str]:
    """Recebe um IQAr e devolve (rótulo, cor_hex) da faixa correspondente."""
    for upper, label, color in IQAR_BANDS:
        if iqar <= upper:
            return label, color
    return IQAR_BANDS[-1][1], IQAR_BANDS[-1][2]


# 2) CSS GLOBAL
#    Injete uma única vez, no topo de cada página, com inject_css().
def inject_css() -> None:
    p = PALETTE
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* ----- base ----- */
        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, sans-serif;
        }}
        .stApp {{ background: {p['bg']}; }}

        /* esconde o menu/rodapé padrão do Streamlit para ficar mais "produto" */
        #MainMenu, footer, header {{ visibility: hidden; }}

        /* largura útil um pouco maior */
        .block-container {{ padding-top: 1.4rem; max-width: 1400px; }}

        /* ----- sidebar ----- */
        section[data-testid="stSidebar"] {{
            background: {p['panel']};
            border-right: 1px solid {p['border']};
        }}
        section[data-testid="stSidebar"] * {{ color: {p['text']}; }}

        /* ----- cards -----
           Usamos st.container(border=True) como card (HTML nativo do Streamlit).
           Estilizamos o wrapper do container em vez de injetar <div> manuais —
           isso evita o bug de a div fechar sozinha entre chamadas de st.markdown. */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: {p['panel']};
            border: 1px solid {p['border']} !important;
            border-radius: 16px;
            padding: 6px 18px 14px 18px;
            margin-bottom: 6px;
        }}
        .card-title {{
            font-size: 0.95rem; font-weight: 600; color: {p['text']};
            margin: 6px 0 12px 0; letter-spacing: .2px;
        }}
        /* .card: só para blocos HTML AUTOCONTIDOS (kpi_card), nunca para envolver
           widgets do Streamlit ao longo de várias chamadas. */
        .card {{
            background: {p['panel']}; border: 1px solid {p['border']};
            border-radius: 16px; padding: 16px 18px;
        }}
        .muted {{ color: {p['muted']}; font-size: .8rem; }}

        /* ----- gauge do IQAr ----- */
        .gauge-num {{ font-size: 2.6rem; font-weight: 800; line-height: 1; }}
        .gauge-unit {{ font-size: .75rem; color: {p['muted']}; letter-spacing: 2px; }}

        /* ----- chat ----- */
        .chat-wrap {{ display: flex; flex-direction: column; gap: 10px; }}
        .bubble {{
            max-width: 85%; padding: 10px 13px; border-radius: 14px;
            font-size: .85rem; line-height: 1.35;
        }}
        .bubble.user {{
            align-self: flex-end; background: {p['brand']}; color: #fff;
            border-bottom-right-radius: 4px;
        }}
        .bubble.bot {{
            align-self: flex-start; background: {p['panel_2']}; color: {p['text']};
            border: 1px solid {p['border']}; border-bottom-left-radius: 4px;
        }}

        /* ----- pipeline do rodapé ----- */
        .pipe {{
            display: flex; align-items: stretch; gap: 0;
            background: {p['panel']}; border: 1px solid {p['border']};
            border-radius: 16px; padding: 16px 8px; margin-top: 10px;
        }}
        .pipe-step {{ flex: 1; padding: 0 18px; }}
        .pipe-step h4 {{ margin: 0 0 4px 0; font-size: .9rem; color: {p['text']}; }}
        .pipe-step p {{ margin: 0; font-size: .76rem; color: {p['muted']}; line-height: 1.35; }}
        .pipe-arrow {{ display: flex; align-items: center; color: {p['muted']}; font-size: 1.2rem; }}

        /* badges de status */
        .pill {{
            display: inline-block; padding: 3px 10px; border-radius: 999px;
            font-size: .72rem; font-weight: 600;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# 3) COMPONENTES VISUAIS PRONTOS
def render_gauge(iqar: float, max_scale: float = 200.0) -> str:
    label, color = classify_iqar(iqar)
    frac = max(0.0, min(iqar / max_scale, 1.0))   # fração do anel a preencher
    r = 52
    circ = 2 * 3.14159 * r
    dash = circ * frac

    return f"""
    <div style="display:flex; align-items:center; gap:18px;">
      <svg width="132" height="132" viewBox="0 0 132 132">
        <circle cx="66" cy="66" r="{r}" fill="none"
                stroke="rgba(255,255,255,.08)" stroke-width="12"/>
        <circle cx="66" cy="66" r="{r}" fill="none"
                stroke="{color}" stroke-width="12" stroke-linecap="round"
                stroke-dasharray="{dash} {circ}"
                transform="rotate(-90 66 66)"/>
        <text x="66" y="62" text-anchor="middle"
              fill="{PALETTE['text']}" font-size="30" font-weight="800">{iqar:.0f}</text>
        <text x="66" y="82" text-anchor="middle"
              fill="{PALETTE['muted']}" font-size="11" letter-spacing="2">IQAr</text>
      </svg>
      <div>
        <div style="font-size:1.5rem; font-weight:700; color:{color};">{label}</div>
        <div class="muted" style="margin-top:6px;">Poluente dominante:<br><b style="color:{PALETTE['text']}">PM2.5</b></div>
      </div>
    </div>
    """


def kpi_card(value: str, label: str, sub: str = "") -> str:
    """Cartãozinho de número simples (usado em Histórico/Previsão)."""
    sub_html = f'<div class="muted" style="margin-top:4px">{sub}</div>' if sub else ""
    return f"""
    <div class="card" style="margin-bottom:0">
      <div style="font-size:1.8rem; font-weight:800; color:{PALETTE['text']}">{value}</div>
      <div class="muted">{label}</div>{sub_html}
    </div>"""
