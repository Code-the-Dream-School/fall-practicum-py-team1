import pandas as pd
import numpy as np
import logging
from core.config import POLLUTANT_COLUMNS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TIME_OF_DAY = {
    k: v for v, k in enumerate(["Morning", "Afternoon", "Evening", "Night"])
}
DAY_OF_WEEK = {
    k: v for v, k in enumerate(["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])
}

def basic_encoding(df: pd.DataFrame) -> pd.DataFrame:
    df["time_of_day"] = df["time_of_day"].replace(TIME_OF_DAY).astype(int)
    df["day_of_week"] = df["day_of_week"].replace(DAY_OF_WEEK).astype(int)
    return df

def get_time_info(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "timestamp" not in df:
        print("Already processed.")
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour"] = df["timestamp"].dt.hour
    df["day"] = df["timestamp"].dt.day
    df["month"] = df["timestamp"].dt.month
    return df

def add_periodicity(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["time_of_day_sin"] = np.sin(df["time_of_day"] * np.pi/ 2)
    df["time_of_day_cos"] = np.cos(df["time_of_day"] * np.pi/ 2)
    df["day_of_week_sin"] = np.sin(2 * df["day_of_week"] * np.pi/ 7)
    df["day_of_week_cos"] = np.cos(2 * df["day_of_week"] * np.pi/ 7)
    df["hour_sin"] = np.sin(df["hour"] * np.pi/ 12)
    df["hour_cos"] = np.cos(df["hour"] * np.pi/ 12)
    df["day_sin"] = np.sin(df["day"] * np.pi/ 15)
    df["day_cos"] = np.cos(df["day"] * np.pi/ 15)
    df["month_sin"] = np.sin(df["month"] * np.pi/ 6)
    df["month_cos"] = np.cos(df["month"] * np.pi/ 6)
    return df

lags = [1, 3, 8, 24]
def add_lagged_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["city", "timestamp"]).reset_index(drop=True)

    df = (
        df.set_index("timestamp")
        .groupby("city")
        .resample("1h") # Fill in missing hours
        .asfreq() # By NaN
        .reset_index()
    )

    g = df.groupby("city")

    # Lagged values of every pollutant
    for col in POLLUTANT_COLUMNS:
        for lag in lags:
            df[f"{col}_lag{lag}"] = g[col].shift(lag)

    # Rolling mean and min/max
    for col in POLLUTANT_COLUMNS:
        df[f"{col}_mean24"] = g[col].transform(lambda s: s.shift(1).rolling(24).mean())
        df[f"{col}_max24"] = g[col].transform(lambda s: s.shift(1).rolling(24).max())
        df[f"{col}_min24"] = g[col].transform(lambda s: s.shift(1).rolling(24).min())

    # Create target values: 24 hours into the future
    for col in POLLUTANT_COLUMNS:
        df[f"{col}_target"] = g[col].shift(-24)

    return df.dropna()

def preprocess_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = basic_encoding(df)         # Encoding the time and day of week
    logger.info(f"Basic encoding completed, data shape: {df.shape}")
    df = get_time_info(df)          # Getting the hour, day and month from timestamp
    logger.info(f"Time info added, data shape: {df.shape}")
    df = add_periodicity(df)        # Add periodicity to time-related features
    logger.info(f"Time periodicity added, data shape: {df.shape}")
    df = add_lagged_data(df)        # Add lagged data from 1, 3, 8 and 24 hours ago, and adding the target value (24-hours in the future)
    logger.info(f"Lagged data and target added, data shape: {df.shape}")

    return df