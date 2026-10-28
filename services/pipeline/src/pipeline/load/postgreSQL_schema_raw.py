import os
from dotenv import load_dotenv
from supabase import create_client

from pipeline.extract.extract import RawRecord, extract


def map_records(records: list[RawRecord]) -> list[dict]:
    """Convert extracted records into rows for the raw database table."""
    rows = []

    for item in records:
        rows.append({
            "dt": item.dt,
            "latitude": item.lat,
            "longitude": item.lon,
            "aqi": item.aqi,
            "co": item.co,
            "no": item.no,
            "no2": item.no2,
            "o3": item.o3,
            "so2": item.so2,
            "pm2_5": item.pm2_5,
            "pm10": item.pm10,
            "nh3": item.nh3,
        })

    return rows


def load_records(records: list[RawRecord], client) -> int:
    """Upsert records and return the number of rows returned by Supabase."""
    rows = map_records(records)

    if not rows:
        print("No observations found.")
        return 0

    response = (
        client.table("air_pollution_raw")
        .upsert(rows, on_conflict="dt,latitude,longitude")
        .execute()
    )

    count = len(response.data or [])
    print(f"Processed {len(rows)} observations.")
    print(f"Rows upserted: {count}")
    return count


def main() -> None:
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

    client = create_client(supabase_url, supabase_key)
    records = extract("current")
    load_records(records, client)


if __name__ == "__main__":
    main()