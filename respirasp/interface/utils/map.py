import pandas as pd
import plotly.graph_objects as go

from styling import PALETTE, classify_iqar, pm25_to_iqar


def stations() -> pd.DataFrame:
    rows = [
        ("Congonhas", -23.626, -46.656, 12),
    ]
    return pd.DataFrame(rows, columns=["estacao", "lat", "lon", "pm25"])

def station_map(df: pd.DataFrame) -> go.Figure:
    colors = [classify_iqar(pm25_to_iqar(v))[1] for v in df["pm25"]]
    fig = go.Figure(go.Scattermap(
        lat=df["lat"], lon=df["lon"], mode="markers+text",
        marker=dict(size=24, color=colors, opacity=0.92),
        text=df["pm25"].astype(int).astype(str),
        textfont=dict(color="#0B1220", size=11, family="Inter"),
        customdata=df["estacao"],
        hovertemplate="<b>%{customdata}</b><br>PM2.5: %{text} µg/m³<extra></extra>"))
    fig.update_layout(
        map=dict(style="open-street-map", center=dict(lat=-23.626, lon=-46.656), zoom=12),
        margin=dict(l=0, r=0, t=0, b=0), height=320, paper_bgcolor="rgba(0,0,0,0)")
    return fig
