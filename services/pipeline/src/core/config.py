from pathlib import Path
from dotenv import load_dotenv

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
