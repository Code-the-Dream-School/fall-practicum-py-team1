
from datetime import datetime, timezone
import os
import logging
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
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

AQI_CATEGORIES = {
    1: "Good",
    2: "Fair",
    3: "Moderate",
    4: "Poor",
    5: "Very Poor",
}


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


# --------------------------------------------------
# Transformation
# --------------------------------------------------


def log_invalid_rows(df):
    """Log rows with invalid required timestamp, coordinate, or AQI values."""
    valid_dt = (
        df["dt"].notna()
        & df["dt"].mod(1).eq(0)
    )
    valid_latitude = df["latitude"].between(-90, 90)
    valid_longitude = df["longitude"].between(-180, 180)
    valid_aqi = (
        df["aqi"].notna()
        & df["aqi"].mod(1).eq(0)
        & df["aqi"].between(1, 5)
    )

    invalid_mask = ~(
        valid_dt
        & valid_latitude
        & valid_longitude
        & valid_aqi
    )
    invalid_rows = df.loc[invalid_mask]

    if not invalid_rows.empty:
        logger.warning(
            "Found %d rows with invalid required values:\n%s",
            len(invalid_rows),
            invalid_rows.to_string(index=False),
        )

    return invalid_mask


def transform(raw_records, locations):
    if not raw_records:
        logger.info("No raw records to transform.")
        return []

    if not locations:
        raise ValueError("The locations table is empty.")

    df = pd.DataFrame(raw_records)

    # Convert numeric fields and remove invalid required values.
    for column in ["dt", "latitude", "longitude", "aqi"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    
    invalid_mask = log_invalid_rows(df)
    df = df.loc[~invalid_mask].copy()

    # Unix timestamps must be whole seconds.
    valid_dt = df["dt"].mod(1).eq(0)
    valid_aqi = df["aqi"].mod(1).eq(0)

    df = df.loc[valid_dt & valid_aqi].copy()

    df["aqi"] = df["aqi"].astype(int)
    df["dt"] = df["dt"].astype("int64")

    df = df[
        df["aqi"].between(1, 5)
        & df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
    ].copy()

    # Convert Unix seconds to UTC-aware timestamps.
    df["timestamp"] = pd.to_datetime(
        df["dt"], unit="s", utc=True, errors="coerce"
    )
    df = df.dropna(subset=["timestamp"]).copy()

    # Clean pollutant measurements.
    for column in POLLUTANT_COLUMNS:
        df[column] = pd.to_numeric(
            df[column], errors="coerce"
        )
        df[column] = df[column].replace(
            [float("inf"), float("-inf")], float("nan")
        )

    # Remove duplicate observations within the raw data.
    df = df.drop_duplicates(
        subset=["dt", "latitude", "longitude"],
        keep="last",
    ).copy()

    # Build coordinate -> location metadata mapping.
    location_map = {}

    for location in locations:
        key = (
            round(float(location["latitude"]), 6),
            round(float(location["longitude"]), 6),
        )

        if key in location_map:
            raise ValueError(
                f"Duplicate coordinates in locations table: {key}"
            )

        # Validate timezone identifiers.
        try:
            ZoneInfo(location["timezone"])
        except (ZoneInfoNotFoundError, KeyError) as exc:
            raise ValueError(
            f"Invalid or missing timezone for location: {location}"
            ) from exc

        location_map[key] = location

    # Match every raw observation to a known location.
    df["location_key"] = list(
        zip(
            df["latitude"].round(6),
            df["longitude"].round(6),
        )
    )

    df["location"] = df["location_key"].map(location_map)

    unmatched = df[df["location"].isna()]
    if not unmatched.empty:
        coords = unmatched[
            ["latitude", "longitude"]
        ].drop_duplicates().to_dict("records")

        raise ValueError(
            "Some raw coordinates have no matching location. "
            f"Add them to the locations table: {coords}"
        )

    df["city"] = df["location"].map(lambda loc: loc["city"])
    df["timezone"] = df["location"].map(
        lambda loc: loc["timezone"]
    )

    # Derive local-time fields and local calendar dates.
    df["local_timestamp"] = [
        timestamp.to_pydatetime().astimezone(ZoneInfo(tz))
        for timestamp, tz in zip(df["timestamp"], df["timezone"])
    ]

    df["time_of_day"] = df["local_timestamp"].map(
        lambda dt: (
            "Morning" if 5 <= dt.hour < 12 else
            "Afternoon" if 12 <= dt.hour < 17 else
            "Evening" if 17 <= dt.hour < 21 else
            "Night"
        )
    )

    df["day_of_week"] = df["local_timestamp"].map(
        lambda dt: dt.strftime("%A")
    )
    df["month"] = df["local_timestamp"].map(
        lambda dt: dt.strftime("%B")
    )
    df["year"] = df["local_timestamp"].map(
        lambda dt: dt.year
    )
    df["local_date"] = df["local_timestamp"].map(
        lambda dt: dt.date().isoformat()
    )

    # Category follows the OpenWeather AQI scale (1–5).
    df["category"] = df["aqi"].map(AQI_CATEGORIES)

    # Derive a 0–100 pollution score from the OpenWeather AQI (1–5).
    df["pollution_score"] = (
        ((df["aqi"] - 1) / 4) * 100
    ).round(2)

    # Calculate a rolling average across the latest 3 observations
    # for each location, ordered by observation time.
    df = df.sort_values(
        ["latitude", "longitude", "timestamp"]
    ).copy()

    df["aqi_rolling_avg"] = (
        df.groupby(["latitude", "longitude"])["aqi"]
        .transform(
            lambda values: values.rolling(
                window=3, min_periods=1
            ).mean()
        ).round(2)
    )

    # Daily AQI statistics by location and local calendar date.
    daily_group = df.groupby(
        ["latitude", "longitude", "local_date"]
    )["aqi"]

    df["daily_max"] = daily_group.transform("max").astype(int)
    df["daily_min"] = daily_group.transform("min").astype(int)
    df["daily_range"] = (
        df["daily_max"] - df["daily_min"]
    ).astype(int)

    # Construct records matching the Gold table schema.
    transformed_at = datetime.now(timezone.utc).isoformat()

    gold_columns = [
        "city", "latitude", "longitude", "timestamp",
        "transformed_at", "aqi",
        *POLLUTANT_COLUMNS,
        "category", "pollution_score", "time_of_day", 
        "day_of_week", "month", "year", "aqi_rolling_avg",
        "daily_max", "daily_min", "daily_range",
    ]

    df["timestamp"] = df["timestamp"].map(
        lambda value: value.isoformat()
    )
    df["transformed_at"] = transformed_at

    gold_df = df[gold_columns].astype(object)
    gold_df = gold_df.where(pd.notna(gold_df), None)

    records = gold_df.to_dict(orient="records")

    logger.info("Transformed %d records.", len(records))
    return records


# --------------------------------------------------
# Load transformed records into Gold
# --------------------------------------------------

def load_gold(client, records, batch_size=500):
    if not records:
        logger.info("No Gold records to write.")
        return

    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]

        (
            client.table(GOLD_TABLE)
            .upsert(
                batch,
                on_conflict="latitude,longitude,timestamp",
            )
            .execute()
        )
        
        logger.info(
        "Upserted %d of %d Gold records.",
        min(start + batch_size, len(records)),
        len(records),
        )

    logger.info("Gold table load completed.")

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    client = create_supabase_client()

    raw_records = fetch_raw_records(client)
    locations = fetch_locations(client)

    gold_records = transform(raw_records, locations)
    load_gold(client, gold_records)


if __name__ == "__main__":
    main()
