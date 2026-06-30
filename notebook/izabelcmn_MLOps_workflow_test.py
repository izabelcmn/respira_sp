import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib
from ml_logic.preprocessor import preprocess_features


df = pd.read_csv(
    "../data/operational/dados_features_engineering_gaps_UTC_20260624.csv",
    index_col=0,
    parse_dates=True
)

df.index = pd.to_datetime(df.index, utc=True)

print(f"\nDados carregados: {df.shape}")
print(f"Período completo: {df.index.min()} → {df.index.max()}")
print(f"NaN total: {df.isna().sum().sum()}")

# Engenharia de features
df_processed = preprocess_features(df)

print(df_processed.shape)
