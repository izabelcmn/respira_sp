"""
utils/charts.py
"""

from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
from utils.styling import PALETTE, classify_iqar, pm25_to_iqar


def _base_layout(height=260):
    return dict(
        height=height, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PALETTE["muted"], family="Inter", size=12),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.06)", zeroline=False),
    )


def obs_vs_pred(context: pd.Series, fc: pd.DataFrame, cut) -> go.Figure:
    """
    Observado (contexto + janela) × Previsto, com linha de corte.
    fc precisa ter: timestamp, yhat e (opcional) y_real.
    Réplica em tema escuro do gráfico matplotlib do notebook operacional.
    """
    fig = go.Figure()

    # contexto observado (antes do corte)
    if context is not None and len(context):
        fig.add_trace(go.Scatter(
            x=context.index, y=context.values, mode="lines",
            name="Observado (72h)", line=dict(color="#5B8DEF", width=1.6),
            hovertemplate="%{x|%d/%m %H:%M}<br>%{y:.1f} µg/m³<extra></extra>"))

    # observado na janela de previsão (se houver)
    if "y_real" in fc.columns and fc["y_real"].notna().any():
        fig.add_trace(go.Scatter(
            x=fc["timestamp"], y=fc["y_real"], mode="lines",
            name="Observado (janela)", line=dict(color="#FB8C00", width=2.4),
            hovertemplate="%{x|%d/%m %H:%M}<br>real %{y:.1f}<extra></extra>"))

    # previsão
    fig.add_trace(go.Scatter(
        x=fc["timestamp"], y=fc["yhat"], mode="lines+markers",
        name="Previsto — LightGBM",
        line=dict(color="#34D399", width=2.4, dash="dash"),
        marker=dict(size=6, color="#34D399"),
        hovertemplate="%{x|%d/%m %H:%M}<br>prev %{y:.1f}<extra></extra>"))

    # linha de corte
    if cut is not None:
        fig.add_vline(x=cut, line=dict(color="#E53935", width=1.5, dash="dot"))

    lay = _base_layout(height=360)
    lay["legend"] = dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                         font=dict(color=PALETTE["text"], size=11))
    fig.update_layout(**lay)
    fig.update_yaxes(title="PM2.5 (µg/m³)", title_font=dict(size=11))
    return fig


def forecast_line(fc: pd.DataFrame) -> go.Figure:
    """Linha compacta da previsão; pontos coloridos pela faixa de IQAr."""
    iqar = fc["yhat"].apply(pm25_to_iqar)
    colors = [classify_iqar(v)[1] for v in iqar]
    fig = go.Figure(go.Scatter(
        x=fc["timestamp"], y=fc["yhat"], mode="lines+markers",
        line=dict(color="#34D399", width=3, shape="spline"),
        marker=dict(size=10, color=colors, line=dict(width=2, color=PALETTE["panel"])),
        hovertemplate="%{x|%H:%M}<br><b>%{y:.0f}</b> µg/m³<extra></extra>"))
    lay = _base_layout(height=240); lay["showlegend"] = False
    fig.update_layout(**lay)
    fig.update_yaxes(title="PM2.5 (µg/m³)", title_font=dict(size=11))
    return fig


def pollutant_bars(values: dict) -> go.Figure:
    names = list(values.keys())[::-1]
    vals = [values[n][0] for n in names]; units = [values[n][1] for n in names]
    ceil = {"PM2.5": 75, "PM10": 150, "O3": 160, "NO2": 200, "CO": 9}
    colors = []
    for n, v in zip(names, vals):
        frac = min(v / ceil.get(n, 100), 1)
        colors.append("#4CAF50" if frac < .4 else "#FBC02D" if frac < .7 else "#FB8C00")
    fig = go.Figure(go.Bar(
        x=vals, y=names, orientation="h", marker=dict(color=colors), width=0.55,
        text=[f"{v:g} {u}" for v, u in zip(vals, units)], textposition="outside",
        textfont=dict(color=PALETTE["text"], size=12), hoverinfo="skip"))
    lay = _base_layout(height=210); lay["showlegend"] = False
    lay["xaxis"]["visible"] = False; lay["yaxis"]["gridcolor"] = "rgba(0,0,0,0)"
    fig.update_layout(**lay); fig.update_xaxes(range=[0, max(vals) * 1.35])
    return fig


def station_map(df: pd.DataFrame) -> go.Figure:
    colors = [classify_iqar(pm25_to_iqar(v))[1] for v in df["pm25"]]
    fig = go.Figure(go.Scattermapbox(
        lat=df["lat"], lon=df["lon"], mode="markers+text",
        marker=dict(size=24, color=colors, opacity=0.92),
        text=df["pm25"].astype(int).astype(str),
        textfont=dict(color="#0B1220", size=11, family="Inter"),
        customdata=df["estacao"],
        hovertemplate="<b>%{customdata}</b><br>PM2.5: %{text} µg/m³<extra></extra>"))
    fig.update_layout(
        mapbox=dict(style="open-street-map", center=dict(lat=-23.59, lon=-46.65), zoom=9.3),
        margin=dict(l=0, r=0, t=0, b=0), height=320, paper_bgcolor="rgba(0,0,0,0)")
    return fig


def history_line(s: pd.Series, color: str = "#3B82F6") -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=s.index, y=s.values, mode="lines", line=dict(color=color, width=1.6),
        hovertemplate="%{x|%d/%m/%Y %H:%M}<br><b>%{y:.0f}</b> µg/m³<extra></extra>"))
    lay = _base_layout(height=340); lay["showlegend"] = False
    fig.update_layout(**lay); fig.update_yaxes(title="PM2.5 (µg/m³)", title_font=dict(size=11))
    return fig
