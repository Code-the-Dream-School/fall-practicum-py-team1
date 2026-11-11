import logging
import pandas as pd
from datetime import datetime, timezone
from model.src.io import create_supabase_client, load_gold, MODELS_DIR

TESTING_DIR = MODELS_DIR / "testing"
RANDOM_STATE = 42

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

def main():
    client = create_supabase_client()
    df = load_gold(client)
    idx_ls = df.sample(n=100, random_state=RANDOM_STATE).index
    sample_df = pd.concat(
        [
            df.loc[
                    (df["city"] == df.loc[idx, "city"]) &
                    (pd.to_datetime(df["timestamp"]) >= pd.to_datetime(df.loc[idx, "timestamp"]) - pd.Timedelta(days=2)) &
                    (pd.to_datetime(df["timestamp"]) <= pd.to_datetime(df.loc[idx, "timestamp"]))
                ]
            for idx in idx_ls
        ]
    )
    sample_df.drop_duplicates().to_parquet(TESTING_DIR / "testing.parquet")

if __name__ == "__main__":
    main()
