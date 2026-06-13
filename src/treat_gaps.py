"""
Tratamento de gaps temporais no PM2.5 - Estação 08 Congonhas

Estratégia:
  ≤ 3h   → interpolação linear
  3-24h  → interpolação cúbica (spline)
  > 24h  → NaN (excluído do treino)

Saída: processed_data/pm25_treated.csv
       índice UTC horário contínuo, 2013-05-09 → fim dos dados CETESB
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "processed_data"


# ── 1. Carregar fontes brutas ─────────────────────────────────────────────────

cetesb = pd.read_csv(DATA / "dados_pm25_estacao8_2013_2019.csv")
cetesb["time"] = (
    pd.to_datetime(cetesb["time"])
    .dt.tz_localize("Etc/GMT+3")   # SP local (POSIX sign-flip: Etc/GMT+3 = UTC-3)
    .dt.tz_convert("UTC")
)
cetesb = cetesb.set_index("time").sort_index()

atm = pd.read_csv(DATA / "openmeteo_historico_2013_2019.csv", index_col=0)
atm.index = pd.to_datetime(atm.index, utc=True)   # converte offsets DST (-02/-03) para UTC


# ── 2. Merge interno ─────────────────────────────────────────────────────────

df = cetesb[["MP2.5"]].join(
    atm[["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m"]],
    how="inner"
)


# ── 3. Reindexar para índice horário UTC contínuo ─────────────────────────────

full_idx = pd.date_range(start=df.index.min(), end=df.index.max(), freq="h", tz="UTC")
df = df.reindex(full_idx)


# ── 4. Tratamento de gaps ─────────────────────────────────────────────────────

def treat_gaps(series: pd.Series) -> tuple[pd.Series, list[dict]]:
    """
    Trata gaps numa série horária contínua.
    Devolve (série_tratada, lista_de_relatório).
    """
    vals = series.values.astype(float).copy()
    n = len(vals)
    report = []

    i = 0
    while i < n:
        if not np.isnan(vals[i]):
            i += 1
            continue

        # encontrar fim do bloco NaN
        j = i
        while j < n and np.isnan(vals[j]):
            j += 1
        gap = j - i                     # duração em horas
        has_left  = i > 0
        has_right = j < n

        if gap <= 3:
            # ── linear ──────────────────────────────────────────────────────
            if has_left and has_right:
                vals[i:j] = np.linspace(vals[i - 1], vals[j], gap + 2)[1:-1]
            elif has_left:
                vals[i:j] = vals[i - 1]
            elif has_right:
                vals[i:j] = vals[j]
            category = "linear"

        elif gap <= 24:
            # ── spline cúbica ────────────────────────────────────────────────
            filled = False
            if has_left and has_right:
                ctx_l = max(0, i - 48)
                ctx_r = min(n, j + 48)
                x_ctx = np.array(
                    [k for k in range(ctx_l, ctx_r) if not np.isnan(vals[k])],
                    dtype=float
                )
                y_ctx = vals[x_ctx.astype(int)]

                if len(x_ctx) >= 4:
                    cs = CubicSpline(x_ctx, y_ctx, extrapolate=False)
                    x_fill = np.arange(i, j, dtype=float)
                    y_fill = np.clip(cs(x_fill), 0.0, None)
                    # rejeitar se NaN (extrapolação falhada) → fallback linear
                    if not np.any(np.isnan(y_fill)):
                        vals[i:j] = y_fill
                        filled = True

                if not filled:
                    # fallback linear
                    vals[i:j] = np.linspace(vals[i - 1], vals[j], gap + 2)[1:-1]
                    category = "spline→linear_fallback"
                else:
                    category = "spline"
            else:
                category = "spline_edge_kept_nan"

        else:
            # ── gap > 24h: mantém NaN ────────────────────────────────────────
            category = "large_nan_kept"

        report.append({
            "inicio":      series.index[i],
            "fim":         series.index[j - 1],
            "duracao_h":   gap,
            "categoria":   category,
        })
        i = j

    return pd.Series(vals, index=series.index, name=series.name), report


pm25_tratado, relatorio = treat_gaps(df["MP2.5"])
df["MP2.5"] = pm25_tratado


# ── 5. Guardar CSV ────────────────────────────────────────────────────────────

out_path = DATA / "pm25_treated.csv"
df.to_csv(out_path)
print(f"Ficheiro guardado: {out_path}")
print(f"Shape: {df.shape}  |  {df.index.min()} → {df.index.max()}")


# ── 6. Relatório ─────────────────────────────────────────────────────────────

rep = pd.DataFrame(relatorio)

print("\n" + "═" * 68)
print(" RELATÓRIO DE TRATAMENTO DE GAPS — PM2.5 Estação 08 Congonhas")
print("═" * 68)

cat_order = ["linear", "spline", "spline→linear_fallback",
             "spline_edge_kept_nan", "large_nan_kept"]

summary = (
    rep.groupby("categoria")
    .agg(num_gaps=("duracao_h", "count"), total_horas=("duracao_h", "sum"))
    .reindex([c for c in cat_order if c in rep["categoria"].values])
)

print(f"\n{'Categoria':<28} {'Nº gaps':>8} {'Horas tratadas':>15}")
print("-" * 54)
for cat, row in summary.iterrows():
    print(f"{cat:<28} {int(row['num_gaps']):>8} {int(row['total_horas']):>15}")

total_gaps  = len(rep)
total_horas = rep["duracao_h"].sum()
nan_restantes = df["MP2.5"].isna().sum()
completude  = df["MP2.5"].notna().mean() * 100

print("-" * 54)
print(f"{'TOTAL':<28} {total_gaps:>8} {int(total_horas):>15}")
print(f"\nNaN remanescentes (gaps > 24h): {nan_restantes} horas")
print(f"Completude final:               {completude:.2f}%")
print(f"Série total:                    {len(df)} horas")

print("\n── Gaps > 24h mantidos como NaN ──────────────────────────────")
grandes = rep[rep["categoria"] == "large_nan_kept"].sort_values("duracao_h", ascending=False)
if len(grandes):
    for _, r in grandes.iterrows():
        dias = r["duracao_h"] / 24
        print(f"  {str(r['inicio'])[:16]}  →  {str(r['fim'])[:16]}   {int(r['duracao_h']):>5}h ({dias:.1f} dias)")
else:
    print("  (nenhum)")

print("\n── Completude PM2.5 por ano ───────────────────────────────────")
df["year"] = df.index.year
for year, g in df.groupby("year"):
    pct = g["MP2.5"].notna().mean() * 100
    bar = "█" * int(pct / 2)
    print(f"  {year}: {pct:5.1f}%  {bar}")
df = df.drop(columns=["year"])

print("═" * 68 + "\n")
