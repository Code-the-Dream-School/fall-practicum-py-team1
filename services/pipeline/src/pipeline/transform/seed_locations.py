
import json
import os
import logging
from pathlib import Path
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from supabase import create_client


BASE_DIR = Path(__file__).resolve().parent

# Find the project root by locating its .env file
PROJECT_ROOT = next(
    (parent for parent in BASE_DIR.parents if (parent / ".env").is_file()),
    None,
)

if PROJECT_ROOT is None:
    raise FileNotFoundError(
        "Could not find .env in the project directory or its parent directories."
    )

load_dotenv(PROJECT_ROOT / ".env")

LOCATIONS_FILE = (
    Path(__file__).resolve().parents[1]
    / "extract"
    / "locations.json"
)

def seed_locations():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be set in .env"
        )

    client = create_client(url, key)

    with LOCATIONS_FILE.open("r", encoding="utf-8") as file:
        locations = json.load(file)["locations"]

    rows = [
        {
            "city": location["city"],
            "state": location["state"],
            "country": location["country"],
            "latitude": location["lat"],
            "longitude": location["lon"],
            "timezone": location["timezone"],
        }
        for location in locations
    ]

    if not rows:
        logger.info("No locations to seed.")
        return

    result = (
        client.table("locations")
        .upsert(
            rows,
            on_conflict="city,latitude,longitude",
        )
        .execute()
    )

    logger.info("Upsert request completed for %d locations.", len(rows))


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    seed_locations()
