import pandas as pd
from model.src.io import load_model_with_metadata
from model.src.train import train
from model.src.preprocess import preprocess_pipeline, USEFUL_FEATURES

def predict(df: pd.DataFrame, pollutant: str) -> pd.Series:
    df = df[USEFUL_FEATURES].copy()
    model, metadata = load_model_with_metadata(pollutant)
    if not model:
        train(targets=[pollutant])
        model, metadata = load_model_with_metadata(pollutant)
    features = metadata["features"]
    df = preprocess_pipeline(df)[features]
    df = df.drop([t for t in df.columns if ("target" in t)], axis=1)
    df.drop(["city", "timestamp"], axis=1, inplace=True)
    return model.predict(df).clip(0)

if __name__ == "__main__":
    from model.testing.create_test import TESTING_DIR
    df = pd.read_parquet(TESTING_DIR / "testing.parquet")
    print(predict(df, "no")[:5])