import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from colorama import Fore, Style


def preprocess_features(X: pd.DataFrame) ->  pd.DataFrame:
    """
    Preprocessor responsible for feature engineering.

    Transforms the cleaned time series dataset into a model-ready feature matrix by
    creating cyclical time features, lagged PM2.5 features, and organizing
    meteorological/exogenous variables.

    The transformation assumes that the input data are ordered chronologically.
    """

    TARGET = "MP2.5"

    MET_VARS = ["temperature_2m","relative_humidity_2m","wind_speed_10m"]

    MET_LAGS = [1, 3, 6, 12, 24]
    PM25_LAGS = [1, 2, 3, 6, 12, 24, 48, 168]
    ROLLING_WINDOWS = [6, 12, 24, 48]

    def add_cyclical_time_features(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("DataFrame index must be a DatetimeIndex.")

        df["month_sin"] = np.sin(2 * np.pi * df.index.month / 12)
        df["month_cos"] = np.cos(2 * np.pi * df.index.month / 12)

        df["weekday_sin"] = np.sin(2 * np.pi * df.index.dayofweek / 7)
        df["weekday_cos"] = np.cos(2 * np.pi * df.index.dayofweek / 7)

        df["hour_sin"] = np.sin(2 * np.pi * df.index.hour / 24)
        df["hour_cos"] = np.cos(2 * np.pi * df.index.hour / 24)

        return df

    def add_meteorological_lags(
        df: pd.DataFrame,
        met_vars: list[str] = MET_VARS,
        lags: list[int] = MET_LAGS,
    ) -> pd.DataFrame:

        df = df.copy()

        for var in met_vars:
            if var in df.columns:
                for lag in lags:
                    df[f"{var}_lag{lag}"] = df[var].shift(lag)

        return df

    def add_pm25_lags(
        df: pd.DataFrame,
        target_col: str = TARGET,
        lags: list[int] = PM25_LAGS,
    ) -> pd.DataFrame:

        df = df.copy()

        if target_col not in df.columns:
            raise ValueError(f"Column '{target_col}' not found in DataFrame.")

        for lag in lags:
            df[f"pm25_lag{lag}"] = df[target_col].shift(lag)

        return df

    def add_seasonal_features(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("DataFrame index must be a DatetimeIndex.")

        df["is_winter"] = df.index.month.isin([6, 7, 8]).astype(int)

        return df

    def add_rolling_pm25_features(
        df: pd.DataFrame,
        target_col: str = TARGET,
        windows: list[int] = ROLLING_WINDOWS,
    ) -> pd.DataFrame:

        df = df.copy()

        if target_col not in df.columns:
            raise ValueError(f"Column '{target_col}' not found in DataFrame.")

        base = df[target_col].shift(1)

        for window in windows:
            df[f"pm25_mean_{window}h"] = base.rolling(window).mean()
            df[f"pm25_std_{window}h"] = base.rolling(window).std()
            df[f"pm25_max_{window}h"] = base.rolling(window).max()

        return df

    print(Fore.BLUE + "\nPreprocessing features..." + Style.RESET_ALL)

    X_processed = X.copy()

    if not isinstance(X_processed.index, pd.DatetimeIndex):
        raise TypeError("X must have a DatetimeIndex.")

    X_processed = X_processed.sort_index()

    X_processed = add_cyclical_time_features(X_processed)
    X_processed = add_meteorological_lags(X_processed)
    X_processed = add_pm25_lags(X_processed)
    X_processed = add_seasonal_features(X_processed)
    X_processed = add_rolling_pm25_features(X_processed)

    X_processed = X_processed.drop(columns=[TARGET])

    # Validate engineered features
    from respirasp.params import LOCAL_REGISTRY_PATH
    features = joblib.load(Path(LOCAL_REGISTRY_PATH) / "lightgbm_features.pkl")

    missing_features = [f for f in features if f not in X_processed.columns]

    if missing_features:
        raise ValueError(
            f"The following required features are missing:\n{missing_features}"
        )

    print(f"✅ All {len(features)} model features are present.")

    print("✅ X_processed shape:", X_processed.shape)

    # Check feature order
    if list(X_processed.columns) != list(features):

        for i, (col_model, col_input) in enumerate(zip(features, X_processed.columns)):
            if col_model != col_input:
                raise ValueError(
                    f"Feature order mismatch at position {i}:\n"
                    f"Expected: '{col_model}'\n"
                    f"Found:    '{col_input}'"
                )

        raise ValueError("Feature order does not match the training feature order.")

    print("✅ Feature order matches the training data.")

    return X_processed
