import os
import numpy as np

##################  VARIABLES  ##################
DATA_SIZE = os.environ.get("DATA_SIZE")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE"))
MODEL_TARGET = os.environ.get("MODEL_TARGET")
GCP_PROJECT = os.environ.get("GCP_PROJECT")
GCP_PROJECT_WAGON = os.environ.get("GCP_PROJECT_WAGON")
GCP_REGION = os.environ.get("GCP_REGION")
BQ_DATASET = os.environ.get("BQ_DATASET")
BQ_REGION = os.environ.get("BQ_REGION")
BUCKET_NAME = os.environ.get("BUCKET_NAME")
INSTANCE = os.environ.get("INSTANCE")
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI")
MLFLOW_EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT")
MLFLOW_MODEL_NAME = os.environ.get("MLFLOW_MODEL_NAME")
PREFECT_FLOW_NAME = os.environ.get("PREFECT_FLOW_NAME")
PREFECT_LOG_LEVEL = os.environ.get("PREFECT_LOG_LEVEL")
EVALUATION_START_DATE = os.environ.get("EVALUATION_START_DATE")
GAR_IMAGE = os.environ.get("GAR_IMAGE")
GAR_MEMORY = os.environ.get("GAR_MEMORY")

##################  CONSTANTS  #####################
LOCAL_DATA_PATH     = os.path.join(os.path.expanduser("~"), "respira_sp", "data")
LOCAL_REGISTRY_PATH = os.path.join(os.path.expanduser("~"), "respira_sp", "training_outputs")

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





################## VALIDATIONS #################

env_valid_options = dict(
    DATA_SIZE=["1k", "200k", "all"],
    MODEL_TARGET=["local", "gcs", "mlflow"],
)

def validate_env_value(env, valid_options):
    env_value = os.environ[env]
    if env_value not in valid_options:
        raise NameError(f"Invalid value for {env} in `.env` file: {env_value} must be in {valid_options}")


for env, valid_options in env_valid_options.items():
    validate_env_value(env, valid_options)
