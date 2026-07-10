import pandas as pd
import plotly.graph_objects as go

from styling import PALETTE, classify_iqar, pm25_to_iqar


# Estação operacional (previsão real do LightGBM) + estações de contexto.
# IMPORTANTE p/ banca: SÓ Congonhas tem previsão do modelo. As demais entram
# como contexto geográfico com valores ILUSTRATIVOS (demo) — trocar por leituras
# reais (CETESB/OpenAQ) se/quando integrar a fonte ao vivo.
def stations() -> pd.DataFrame:
    rows = [
        # estacao,       lat,      lon,     pm25, operacional
        ("Congonhas",   -23.626, -46.656,  12,  True),   # <- previsão real
        ("Pinheiros",   -23.561, -46.702,  62,  False),  # demo
        ("Santana",     -23.503, -46.628,  48,  False),  # demo
        ("Lapa",        -23.522, -46.705,  52,  False),  # demo
        ("Tatuapé",     -23.540, -46.576,  55,  False),  # demo
        ("Moema",       -23.601, -46.663,  70,  False),  # demo
        ("Parelheiros", -23.827, -46.728,  45,  False),  # demo
        ("Guarulhos",   -23.454, -46.533,  58,  False),  # demo
        ("Osasco",      -23.532, -46.792,  60,  False),  # demo
    ]
    return pd.DataFrame(
        rows, columns=["estacao", "lat", "lon", "pm25", "operacional"])


def station_map(df: pd.DataFrame) -> go.Figure:
    # tolera dataframe antigo sem a coluna 'operacional'
    if "operacional" not in df.columns:
        df = df.assign(operacional=df["estacao"].eq("Congonhas"))

    outras = df[~df["operacional"]]
    congon = df[df["operacional"]]

    fig = go.Figure()

    # ── estações de contexto (demo): menores e semitransparentes ──────────────
    if not outras.empty:
        cor_contexto = "#F97316"

        fig.add_trace(go.Scattermap(
            lat=outras["lat"],
            lon=outras["lon"],
            mode="markers",
            marker=dict(
                size=18,
                color=cor_contexto,
                opacity=0.85,
            ),
            text=outras["pm25"].astype(int).astype(str),
            customdata=outras["estacao"],
            hovertemplate=(
                "<b>%{customdata}</b> (demo)"
                "<br>PM2.5: %{text} µg/m³<extra></extra>"
            ),
        ))

    # ── Congonhas: anel branco + marcador maior + valor (é a estação real) ────
    if not congon.empty:
        cor_c = [classify_iqar(pm25_to_iqar(v))[1] for v in congon["pm25"]]
        # anel branco (marcador maior atrás, simula uma borda de destaque)
        fig.add_trace(go.Scattermap(
            lat=congon["lat"], lon=congon["lon"], mode="markers",
            marker=dict(size=40, color="#FFFFFF", opacity=0.9),
            hoverinfo="skip"))
        # marcador colorido por cima, com o valor
        fig.add_trace(go.Scattermap(
            lat=congon["lat"], lon=congon["lon"], mode="markers+text",
            marker=dict(size=30, color=cor_c, opacity=1.0),
            text=congon["pm25"].astype(int).astype(str),
            textfont=dict(color="#0B1220", size=12, family="Inter"),
            customdata=congon["estacao"],
            hovertemplate="<b>%{customdata}</b> — previsão do modelo"
                          "<br>PM2.5: %{text} µg/m³<extra></extra>"))

    fig.update_layout(
        map=dict(style="open-street-map",
                 center=dict(lat=-23.626, lon=-46.656), zoom=10.2),
        margin=dict(l=0, r=0, t=0, b=0), height=320,
        paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
    return fig
