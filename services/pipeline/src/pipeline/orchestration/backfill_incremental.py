
"""
Select Gold records for backfill or incremental enrichment.

This module selects eligible records from air_pollution_gold
that have not been successfully enriched for the current
prompt version.

It does not call OpenAI or save enrichment results.
"""

from datetime import date, datetime, time, timedelta, timezone
import math
from typing import Any, Iterator

GOLD_TABLE = "air_pollution_gold"
ENRICHMENT_TABLE = "air_pollution_enrichment"

DEFAULT_PROMPT_VERSION = "v1"
DEFAULT_BATCH_SIZE = 100
PAGE_SIZE = 1000

POLLUTANT_COLUMNS = (
    "co",
    "no",
    "no2",
    "o3",
    "so2",
    "pm2_5",
    "pm10",
    "nh3",
)


def parse_date(value: str | date) -> date:
    """Convert a YYYY-MM-DD string or date to a date."""
    if isinstance(value, datetime):
        raise ValueError("Use a date, not a datetime.")

    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid date: {value}. Use YYYY-MM-DD."
        ) from exc


def validate_mode_dates(
    mode: str,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
) -> tuple[date, date] | None:
    """Validate the selected mode and its date arguments."""

    if mode not in ("backfill", "incremental"):
        raise ValueError(
            "mode must be 'backfill' or 'incremental'."
        )

    if mode == "incremental":
        if start_date is not None or end_date is not None:
            raise ValueError(
                "Do not provide dates for incremental mode."
            )
        return None

    if start_date is None or end_date is None:
        raise ValueError(
            "Backfill requires both start_date and end_date."
        )

    start = parse_date(start_date)
    end = parse_date(end_date)

    if end < start:
        raise ValueError(
            "end_date cannot be earlier than start_date."
        )

    return start, end


def is_finite_number(value: Any) -> bool:
    """Check whether a value is a finite number."""
    if isinstance(value, bool):
        return False

    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def is_valid_timestamp(value: Any) -> bool:
    """Check that a timestamp is valid and timezone-aware."""

    if isinstance(value, datetime):
        return (
            value.tzinfo is not None
            and value.utcoffset() is not None
        )

    if not isinstance(value, str):
        return False

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        return (
            parsed.tzinfo is not None
            and parsed.utcoffset() is not None
        )
    except ValueError:
        return False


def is_eligible_record(record: dict[str, Any]) -> bool:
    """
    Apply the eligibility rules from the enrichment contract.

    A record needs:
    - A nonempty city
    - Valid latitude and longitude
    - A valid timezone-aware timestamp
    - An integer AQI between 1 and 5
    - At least one finite pollutant measurement
    """

    city = record.get("city")

    if not isinstance(city, str) or not city.strip():
        return False

    latitude = record.get("latitude")
    longitude = record.get("longitude")

    if not is_finite_number(latitude):
        return False

    if not is_finite_number(longitude):
        return False

    if not -90 <= float(latitude) <= 90:
        return False

    if not -180 <= float(longitude) <= 180:
        return False

    if not is_valid_timestamp(record.get("timestamp")):
        return False

    aqi = record.get("aqi")

    if isinstance(aqi, bool) or not isinstance(aqi, int):
        return False

    if not 1 <= aqi <= 5:
        return False

    return any(
        is_finite_number(record.get(column))
        for column in POLLUTANT_COLUMNS
    )


def normalize_timestamp(value: Any) -> str:
    """Normalize a timestamp to UTC for consistent key comparison."""

    if isinstance(value, str):
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise ValueError("Invalid timestamp.")

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must include timezone information.")

    return (
        parsed.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def build_enrichment_key(
    record: dict[str, Any],
    prompt_version: str,
) -> tuple[float, float, str, str]:
    """
    Build the four-column enrichment identity.

    Model is deliberately excluded from this key.
    """

    return (
        float(record["latitude"]),
        float(record["longitude"]),
        normalize_timestamp(record["timestamp"]),
        prompt_version,
    )


def fetch_gold_records(
    supabase: Any,
    mode: str,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Fetch Gold records, using pagination."""

    date_range = validate_mode_dates(
        mode, start_date, end_date
    )

    if page_size < 1:
        raise ValueError("page_size must be at least 1.")

    query = (
        supabase.table(GOLD_TABLE)
        .select("*")
        .order("timestamp")
        .order("latitude")
        .order("longitude")
    )

    if date_range is not None:
        start, end = date_range

        start_utc = datetime.combine(
            start, time.min, tzinfo=timezone.utc
        )

        # Exclusive upper bound includes the entire end date.
        end_exclusive_utc = datetime.combine(
            end + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )

        query = (
            query
            .gte("timestamp", start_utc.isoformat())
            .lt("timestamp", end_exclusive_utc.isoformat())
        )

    all_rows = []
    offset = 0

    while True:
        response = (
            query
            .range(offset, offset + page_size - 1)
            .execute()
        )

        rows = response.data or []
        all_rows.extend(rows)

        if len(rows) < page_size:
            break

        offset += page_size

    return all_rows


def fetch_successful_enrichment_keys(
    supabase: Any,
    prompt_version: str,
    page_size: int = PAGE_SIZE,
) -> set[tuple[float, float, str, str]]:
    """
    Fetch only successful enrichment identities for this prompt version.

    Failed and pending records are not treated as completed.
    Model is metadata and is not part of the identity.
    """

    if page_size < 1:
        raise ValueError("page_size must be at least 1.")

    query = (
        supabase.table(ENRICHMENT_TABLE)
        .select("latitude,longitude,timestamp,prompt_version")
        .eq("status", "success")
        .eq("prompt_version", prompt_version)
        .order("timestamp")
        .order("latitude")
        .order("longitude")
    )

    successful_keys = set()
    offset = 0

    while True:
        response = (
            query
            .range(offset, offset + page_size - 1)
            .execute()
        )

        rows = response.data or []

        for row in rows:
            successful_keys.add(
                build_enrichment_key(row, prompt_version)
            )

        if len(rows) < page_size:
            break

        offset += page_size

    return successful_keys


def select_records_for_enrichment(
    gold_records: list[dict[str, Any]],
    successful_keys: set[tuple[float, float, str, str]],
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> list[dict[str, Any]]:
    """
    Select eligible records not already successfully enriched.

    A failed or pending enrichment does not appear in successful_keys,
    so its Gold record remains eligible.
    """

    selected = []

    for record in gold_records:
        if not is_eligible_record(record):
            continue

        key = build_enrichment_key(record, prompt_version)

        if key not in successful_keys:
            selected.append(record)

    return selected


def iter_batches(
    records: list[dict[str, Any]],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Iterator[list[dict[str, Any]]]:
    """Split selected records into manageable batches."""

    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    for start in range(0, len(records), batch_size):
        yield records[start:start + batch_size]


def get_records_to_enrich(
    supabase: Any,
    mode: str,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    """
    Main entry point for backfill and incremental selection.

    Returns eligible Gold records that need enrichment.
    """

    validate_mode_dates(mode, start_date, end_date)

    gold_records = fetch_gold_records(
        supabase=supabase,
        mode=mode,
        start_date=start_date,
        end_date=end_date,
        page_size=page_size,
    )

    successful_keys = fetch_successful_enrichment_keys(
        supabase=supabase,
        prompt_version=prompt_version,
        page_size=page_size,
    )

    selected = select_records_for_enrichment(
        gold_records=gold_records,
        successful_keys=successful_keys,
        prompt_version=prompt_version,
    )

    print(f"Mode: {mode}")
    print(f"Gold records fetched: {len(gold_records)}")
    print(f"Successful enrichment keys: {len(successful_keys)}")
    print(f"Records selected: {len(selected)}")

    return selected
