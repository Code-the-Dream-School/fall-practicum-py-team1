import pandas as pd
import logging
import lightgbm as lgb
import json
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import root_mean_squared_error as rmse
from lightgbm import LGBMRegressor
from datetime import datetime, timezone

from core.io import create_supabase_client
from core.config import POLLUTANT_COLUMNS
from model.config import MODELS_DIR
from model.src.io import load_gold
from model.src.preprocess import preprocess_pipeline, USEFUL_FEATURES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def load_train() -> pd.DataFrame:
    client = create_supabase_client()
    df = load_gold(client)
    return df

def baseline_model(df: pd.DataFrame, target: str):
    return df[target.rsplit("_", 1)[0]]

def model_train(df: pd.DataFrame, target: str) -> pd.DataFrame:
    if "target" not in target:
        logger.error(f"Incorret target name {target}, 'target' should be in the string")
        raise KeyError(f"Incorret target name {target}, 'target' should be in the string")
    df = df.copy()
    df = df.drop([t for t in df.columns if ("target" in t) and t != target], axis=1)
    df = df.sort_values("timestamp")
    cutoff = df["timestamp"].max() - pd.Timedelta(days=60)
    train, test = df[df.timestamp < cutoff], df[df.timestamp >= cutoff]
    train.drop(["city", "timestamp"], axis=1, inplace=True)
    test.drop(["city", "timestamp"], axis=1, inplace=True)

    X_train, y_train = train.drop(target, axis=1), train[target]
    X_test, y_test = test.drop(target, axis=1), test[target]
    model = LGBMRegressor()
    logger.info("Training started...")
    model.fit(X_train, y_train)
    logger.info("Training completed")
    y_train_hat = model.predict(X_train)
    logger.info(f"Training error: {round(rmse(y_train, y_train_hat), 2)}, baseline training error: {round(rmse(y_train, baseline_model(train, target)), 2)}")
    y_test_hat = model.predict(X_test)
    test_error = round(rmse(y_test, y_test_hat), 2)
    logger.info(f"Testing error: {test_error}, baseline testing error: {round(rmse(y_test, baseline_model(test, target)), 2)} ")
    return model, test_error

def save_model_with_metadata(booster: lgb.Booster, df: pd.DataFrame, params: dict, pollutant: str) -> tuple:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODELS_DIR / "models" / f"{pollutant}.txt"
    meta_path = MODELS_DIR / "models" /  f"{pollutant}_meta.json"

    booster.save_model(str(model_path))

    meta = {
        "pollutant": pollutant,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "lightgbm_version": lgb.__version__,
        "features": [f for f in list(df.columns) if "_target" not in f],
        "params": params,
        "n_train_rows": int(len(df)),
    }

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)

    return model_path, meta_path

def train(targets: list[str]=POLLUTANT_COLUMNS):
    client = create_supabase_client()
    logger.info("Start loading data from Supabase...")
    df = load_gold(client)[USEFUL_FEATURES]
    df = df.loc[pd.to_datetime(df["timestamp"]) >= pd.Timestamp(2025, 4, 1, tz="UTC")]      # Data post 2025 April is clean
    logger.info(f"Raw training data loaded, data shape: {df.shape}")
    df = preprocess_pipeline(df)
    logger.info(f"Preprocessing completed, data shape: {df.shape}")
    models = {}
    errors = {}
    for pollutant in targets:
        target = pollutant + "_target"
        logger.info(f"Training info for {pollutant}:")
        model, error = model_train(df, target)   
        print()
        models[pollutant] = model
        errors[pollutant] = error
        model_path, meta_path = save_model_with_metadata(model.booster_, df, model.get_params(), pollutant)
        logger.info(f"Model saved at {model_path} with metadata at {meta_path}")
    logger.info("All training completed")
    display_df = df[POLLUTANT_COLUMNS].mean().to_frame(name="mean")
    display_df["rmse"] = errors

if __name__ == "__main__":
    train()