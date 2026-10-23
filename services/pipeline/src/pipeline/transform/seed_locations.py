
import json
import os
from pathlib import Path

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

LOCATIONS_FILE = PROJECT_ROOT / "locations.json"


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

    # Read existing location coordinates
    response = (
        client.table("locations")
        .select("latitude, longitude")
        .execute()
    )

    existing = {
        (round(float(row["latitude"]), 6),
         round(float(row["longitude"]), 6))
        for row in response.data
    }

    rows_to_insert = []

    for location in locations:
        coordinates = (
            round(float(location["lat"]), 6),
            round(float(location["lon"]), 6),
        )

        if coordinates in existing:
            print(f"Already exists: {location['city']}")
            continue

        rows_to_insert.append({
            "city": location["city"],
            "state": location["state"],
            "country": location["country"],
            "latitude": location["lat"],
            "longitude": location["lon"],
            "timezone": location["timezone"],
        })

        existing.add(coordinates)

    if not rows_to_insert:
        print("No new locations to insert.")
        return

    result = (
        client.table("locations")
        .insert(rows_to_insert)
        .execute()
    )

    print(f"Inserted {len(result.data)} location(s).")

    for row in result.data:
        print(f"- {row['city']}")


if __name__ == "__main__":
    seed_locations()
