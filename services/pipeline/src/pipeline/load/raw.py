import os
from datetime import datetime, timezone

import psycopg


class RawLoadError(Exception):
    """Raised when raw records cannot be written to the database."""


def load_raw(records: list[dict]) -> int:
    """Upsert raw air-pollution records into PostgreSQL.

    Record identity is (dt, latitude, longitude), matching the
    air_pollution_raw primary key. Repeated records update existing rows.

    Returns the number of records processed.
    """
    if not records:
        return 0

    required_fields = {
        "latitude",
        "longitude",
        "aqi",
        "co",
        "no",
        "no2",
        "o3",
        "so2",
        "pm2_5",
        "pm10",
        "nh3",
    }

    rows = []
    for index, record in enumerate(records):
        missing = required_fields - record.keys()
        if missing:
            raise ValueError(
                f"Record {index} is missing required fields: "
                f"{', '.join(sorted(missing))}"
            )

        if "dt" in record:
            dt = record["dt"]
        elif "timestamp" in record:
            timestamp = record["timestamp"]
            if isinstance(timestamp, datetime):
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                dt = int(timestamp.timestamp())
            elif isinstance(timestamp, str):
                dt = int(datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                ).timestamp())
            else:
                raise ValueError(
                    f"Record {index} has an invalid timestamp"
                )
        else:
            raise ValueError(
                f"Record {index} must contain 'dt' or 'timestamp'"
            )

        rows.append((
            dt,
            record["latitude"],
            record["longitude"],
            record["aqi"],
            record["co"],
            record["no"],
            record["no2"],
            record["o3"],
            record["so2"],
            record["pm2_5"],
            record["pm10"],
            record["nh3"],
        ))

    try:
        with psycopg.connect(
            host=os.environ["SUPABASE_DB_HOST"],
            port=int(os.getenv("SUPABASE_DB_PORT", "5432")),
            dbname=os.environ["SUPABASE_DB_NAME"],
            user=os.environ["SUPABASE_DB_USER"],
            password=os.environ["SUPABASE_DB_PASSWORD"],
            sslmode="require",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO public.air_pollution_raw (
                        dt, latitude, longitude, aqi,
                        co, no, no2, o3, so2, pm2_5, pm10, nh3
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (dt, latitude, longitude)
                    DO UPDATE SET
                        aqi = EXCLUDED.aqi,
                        co = EXCLUDED.co,
                        no = EXCLUDED.no,
                        no2 = EXCLUDED.no2,
                        o3 = EXCLUDED.o3,
                        so2 = EXCLUDED.so2,
                        pm2_5 = EXCLUDED.pm2_5,
                        pm10 = EXCLUDED.pm10,
                        nh3 = EXCLUDED.nh3
                    """,
                    rows,
                )
        return len(rows)
    except Exception as exc:
        raise RawLoadError(
            f"Failed to write {len(rows)} raw record(s) to PostgreSQL."
        ) from exc
