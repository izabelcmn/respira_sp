"""
pages/1_Previsão.py
"""

import pandas as pd
import streamlit as st

from utils.styling import inject_css, kpi_card, classify_iqar, pm25_to_iqar
from utils.data import lightgbm_forecast, LGBM_OPERATIONAL, BACKTEST_2019, STATION, TRAIN_PERIOD
from utils.charts import obs_vs_pred

st.set_page_config(page_title="Previsão · Respira SP", page_icon="📈", layout="wide")
inject_css()

st.markdown("## 📈 Previsão de PM2.5 (24h) — LightGBM operacional")
st.markdown(f'<p class="muted">Modelo treinado em {STATION} ({TRAIN_PERIOD}), aplicado '
            f'a dados reais recentes. Previsão direta de 24h (sem autorregressão).</p>',
            unsafe_allow_html=True)

bundle = lightgbm_forecast(n=24)
fc = bundle["forecast"]
m = bundle["metrics"] or LGBM_OPERATIONAL
is_live = bundle["source"] == "lightgbm"

if not is_live:
    st.info("Modo demo (sintético): copie `lightgbm_pm25.pkl`, `lightgbm_features.pkl` "
            "para `models/` e o CSV para `data/operational/` no repo para ativar o modelo real.",
            icon="🟡")

# --- KPIs (as 6 métricas do notebook) ---
c1, c2, c3 = st.columns(3)
c1.markdown(kpi_card(f"{m['mae']:.2f}", "MAE (µg/m³)",
                     f"validação 2018: {LGBM_OPERATIONAL['mae_val2018']:.2f}"), unsafe_allow_html=True)
c2.markdown(kpi_card(f"{m['rmse']:.2f}", "RMSE (µg/m³)"), unsafe_allow_html=True)
c3.markdown(kpi_card(f"{m['r2']:.3f}", "R²", "janela única / ar limpo"), unsafe_allow_html=True)
c4, c5, c6 = st.columns(3)
mbe = m["mbe"]
c4.markdown(kpi_card(f"{mbe:+.2f}", "MBE (µg/m³)",
                     "superestima" if mbe > 0 else "subestima"), unsafe_allow_html=True)
c5.markdown(kpi_card(f"{m['nmae']:.1f}%", "NMAE", "MAE / média observada"), unsafe_allow_html=True)
c6.markdown(kpi_card(f"{m['mape']:.0f}%", "MAPE", "inflado por valores ~0 → não use"),
            unsafe_allow_html=True)

st.write("")  # respiro

# --- Gráfico observado × previsto ---
with st.container(border=True):
    st.markdown('<div class="card-title">Observado × Previsto</div>', unsafe_allow_html=True)
    st.plotly_chart(obs_vs_pred(bundle["context"], fc, bundle["cut"]),
                    width="stretch", config={"displayModeBar": False})

st.info(
    f"**Leitura para a banca:** o modelo treinado em {TRAIN_PERIOD} mantém o erro "
    f"absoluto controlado mesmo ~7 anos depois (MAE {LGBM_OPERATIONAL['mae_val2018']:.2f} → "
    f"{LGBM_OPERATIONAL['mae']:.2f} µg/m³). O R² baixo e o MAPE altíssimo vêm de uma "
    f"janela de **ar limpo** (média ≈ {LGBM_OPERATIONAL['mean_obs']:.1f} µg/m³): pouca "
    f"variância para explicar e divisões por valores próximos de zero — não indicam falha do modelo.",
    icon="🎓")

# --- Backtest histórico 2019 (CONTEXTO, não comparável ao operacional) ---
st.markdown("### Backtest histórico (walk-forward, 2019)")
st.markdown('<p class="muted">Regime de avaliação diferente do operacional acima — '
            'NÃO compare os R² diretamente.</p>', unsafe_allow_html=True)

rows = [{"Modelo": k, "R² (2019)": v["r2"], "Observação": v["note"]}
        for k, v in BACKTEST_2019.items()]
df = pd.DataFrame(rows).sort_values("R² (2019)", ascending=False)
st.dataframe(df, width="stretch", hide_index=True,
             column_config={"R² (2019)": st.column_config.ProgressColumn(
                 "R² (2019)", format="%.3f", min_value=0.0, max_value=0.5)})
