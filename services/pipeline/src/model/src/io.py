import pandas as pd
import logging
import json
import lightgbm as lgb

from supabase import Client
from core.config import GOLD_COLUMNS
from core.io import create_supabase_client, fetch_gold_records

from model.config import MODELS_DIR
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

def load_gold(client: Client) -> pd.DataFrame:
    client = create_supabase_client()
    rows = fetch_gold_records(client)
    logger.info(f"{len(rows)} rows fetched from gold table")
    return pd.DataFrame(
        rows,
        columns=GOLD_COLUMNS
    )

def load_model_with_metadata(pollutant: str):
    booster = None
    meta = None
    model_meta_path = MODELS_DIR / "models" / f"{pollutant}_meta.json"
    model_path = MODELS_DIR / "models" / f"{pollutant}.txt"
    if not model_meta_path.exists():
        logger.error(f"{model_meta_path} not exists, training has to be done first")
        return booster, meta
    if not model_path.exists():
        logger.error(f"{model_path} not exists, training has to be done first")
        return booster, meta
    with open(model_meta_path, "r") as f:
            meta = json.load(f)
    booster = lgb.Booster(model_file=str(model_path))
    
    return booster, meta