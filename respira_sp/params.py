import os
import numpy as np

##################  VARIABLES  ##################
MODEL_TARGET = os.environ.get("MODEL_TARGET", "local")

##################  CONSTANTS  #####################
LOCAL_DATA_PATH     = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LOCAL_REGISTRY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

COLUMN_NAMES_RAW = [
    "time",
    "PM2.5",
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
]

DTYPES_RAW = {
    "time":                 "datetime64[ns, UTC]",
    "PM2.5":                "float32",
    "temperature_2m":       "float32",
    "relative_humidity_2m": "float32",
    "precipitation":        "float32",
    "wind_speed_10m":       "float32",
}

DTYPES_PROCESSED = np.float32

FEATURE_NAMES = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "month_sin", "month_cos",
    "weekday_sin", "weekday_cos",
    "hour_sin", "hour_cos",
    "pm25_lag1", "pm25_lag3", "pm25_lag6", "pm25_lag12", "pm25_lag24",
    "temperature_2m_lag1", "temperature_2m_lag3",
    "temperature_2m_lag6", "temperature_2m_lag12", "temperature_2m_lag24",
    "relative_humidity_2m_lag1", "relative_humidity_2m_lag3",
    "relative_humidity_2m_lag6", "relative_humidity_2m_lag12", "relative_humidity_2m_lag24",
    "wind_speed_10m_lag1", "wind_speed_10m_lag3",
    "wind_speed_10m_lag6", "wind_speed_10m_lag12", "wind_speed_10m_lag24",
    "is_winter",
]

HORIZON = 24

################## VALIDATIONS #################

env_valid_options = dict(
    MODEL_TARGET=["local", "gcs", "mlflow"],
)

def validate_env_value(env, valid_options):
    env_value = os.environ.get(env)
    if env_value and env_value not in valid_options:
        raise NameError(
            f"Invalid value for {env} in `.env` file: {env_value} must be in {valid_options}"
        )


for env, valid_options in env_valid_options.items():
    validate_env_value(env, valid_options)
