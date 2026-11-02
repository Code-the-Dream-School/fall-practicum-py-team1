import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client
logger = logging.getLogger(__name__)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

PROJECT_ROOT = next(
    (
        parent
        for parent in BASE_DIR.parents
        if (parent / ".env").is_file()
    ),
    None,
)

if PROJECT_ROOT is not None:
    load_dotenv(PROJECT_ROOT / ".env")


RAW_TABLE = "air_pollution_raw"
LOCATIONS_TABLE = "locations"
GOLD_TABLE = "air_pollution_gold"

RAW_COLUMNS = [
    "dt", "latitude", "longitude", "aqi",
    "co", "no", "no2", "o3", "so2",
    "pm2_5", "pm10", "nh3",
]

POLLUTANT_COLUMNS = [
    "co", "no", "no2", "o3", "so2",
    "pm2_5", "pm10", "nh3",
]

# --------------------------------------------------
# Supabase connection and data retrieval
# --------------------------------------------------

def create_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be configured in .env"
        )

    return create_client(url, key)


def fetch_all_rows(client, table, columns, page_size=1000):
    """Fetch every row using pagination.
       Supabase queries have a default 1,000-row limit.
       Pagination ensures we fetch all rows in batches.
    """
    rows = []
    start = 0

    while True:
        response = (
            client.table(table)
            .select(columns)
            .range(start, start + page_size - 1)
            .execute()
        )

        batch = response.data
        rows.extend(batch)

        if len(batch) < page_size:
            break

        start += page_size

    logger.info("Read %d rows from %s", len(rows), table)
    return rows


def fetch_raw_records(client):
    return fetch_all_rows(
        client,
        RAW_TABLE,
        ", ".join(RAW_COLUMNS),
    )


def fetch_locations(client):
    return fetch_all_rows(
        client,
        LOCATIONS_TABLE,
        "city,state,country,latitude,longitude,timezone",
    )
