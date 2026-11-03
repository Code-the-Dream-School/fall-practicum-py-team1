import pandas as pd
import logging

from supabase import Client
from core.config import GOLD_COLUMNS
from core.io import create_supabase_client, fetch_gold_records
logger = logging.getLogger(__name__)

def load_gold(client: Client) -> pd.DataFrame:
    client = create_supabase_client()
    rows = fetch_gold_records(client)
    logger.info(f"{len(rows)} rows fetched from gold table")
    return pd.DataFrame(
        rows,
        columns=GOLD_COLUMNS
    )    