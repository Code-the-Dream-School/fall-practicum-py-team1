import logging
import os
from datetime import datetime, timezone

from supabase import create_client

from pipeline.enrichment.client import AirQualityEnricher
from pipeline.enrichment.config import OPENAI_MODEL, PROMPT_VERSION


logger = logging.getLogger(__name__)

GOLD_TABLE = "air_pollution_gold"
ENRICHMENT_TABLE = "air_pollution_enrichment"

GOLD_COLUMNS = (
    "city,latitude,longitude,timestamp,aqi,category,"
    "co,no,no2,o3,so2,pm2_5,pm10,nh3,pollution_score"
)

ENRICHMENT_COLUMNS = (
    "latitude,longitude,timestamp,prompt_version,"
    "status,attempt_count"
)

CONFLICT_COLUMNS = "latitude,longitude,timestamp,prompt_version"


def create_supabase_client():
    """Create a Supabase client using environment variables."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be configured in .env"
        )

    return create_client(url, key)


def fetch_all_rows(client, table, columns, page_size=1000):
    """Fetch all rows from a Supabase table using pagination."""
    rows = []
    start = 0

    while True:
        response = (
            client.table(table)
            .select(columns)
            .range(start, start + page_size - 1)
            .execute()
        )

        batch = response.data or []
        rows.extend(batch)

        if len(batch) < page_size:
            break

        start += page_size

    logger.info("Read %d rows from %s", len(rows), table)
    return rows


def normalize_timestamp(value):
    """Normalize a timestamp to a UTC ISO-format string."""
    if isinstance(value, datetime):
        timestamp = value
    else:
        timestamp = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return timestamp.astimezone(timezone.utc).isoformat()


def build_record_key(record, prompt_version):
    """Build the unique identity for one enrichment record."""
    return (
        float(record["latitude"]),
        float(record["longitude"]),
        normalize_timestamp(record["timestamp"]),
        prompt_version,
    )


def fetch_existing_enrichments(client, prompt_version):
    """Fetch existing enrichment records for the current prompt version."""
    rows = fetch_all_rows(
        client,
        ENRICHMENT_TABLE,
        ENRICHMENT_COLUMNS,
    )

    existing = {}

    for row in rows:
        if row["prompt_version"] != prompt_version:
            continue

        key = build_record_key(row, prompt_version)
        existing[key] = row

    logger.info(
        "Found %d existing enrichment records for prompt %s",
        len(existing),
        prompt_version,
    )

    return existing


def save_enrichment(
    client,
    record,
    result,
    status,
    model,
    prompt_version,
    attempt_count,
    error_message=None,
):
    """Insert or update one enrichment record."""
    payload = {
        "latitude": record["latitude"],
        "longitude": record["longitude"],
        "timestamp": normalize_timestamp(record["timestamp"]),
        "model": model,
        "prompt_version": prompt_version,
        "result": result,
        "status": status,
        "error_message": error_message,
        "attempt_count": attempt_count,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    client.table(ENRICHMENT_TABLE).upsert(
        payload,
        on_conflict=CONFLICT_COLUMNS,
    ).execute()


def run_enrichment(
    supabase_client=None,
    enricher=None,
    model=OPENAI_MODEL,
    prompt_version=PROMPT_VERSION,
):
    """Enrich Gold observations and save results incrementally."""

    if supabase_client is None:
        supabase_client = create_supabase_client()

    if enricher is None:
        enricher = AirQualityEnricher(model=model)

    gold_records = fetch_all_rows(
        supabase_client,
        GOLD_TABLE,
        GOLD_COLUMNS,
    )

    existing = fetch_existing_enrichments(
        supabase_client,
        prompt_version,
    )

    summary = {
        "total": len(gold_records),
        "skipped": 0,
        "succeeded": 0,
        "failed": 0,
    }

    processed_keys = set()

    for record in gold_records:
        key = build_record_key(record, prompt_version)

        if key in processed_keys:
            summary["skipped"] += 1
            continue

        processed_keys.add(key)

        previous = existing.get(key)

        if previous and previous["status"] == "success":
            summary["skipped"] += 1
            continue

        attempt_count = (
            previous["attempt_count"] if previous else 0
        ) + 1

        save_enrichment(
            supabase_client,
            record,
            result=None,
            status="pending",
            model=model,
            prompt_version=prompt_version,
            attempt_count=attempt_count,
        )

        try:
            result = enricher.enrich(record)
        except Exception as exc:
            error_message = str(exc)[:2000]

            save_enrichment(
                supabase_client,
                record,
                result=None,
                status="failed",
                model=model,
                prompt_version=prompt_version,
                attempt_count=attempt_count,
                error_message=error_message,
            )

            logger.exception(
                "Enrichment failed for timestamp %s",
                record["timestamp"],
            )
            summary["failed"] += 1
            continue

        save_enrichment(
            supabase_client,
            record,
            result=result,
            status="success",
            model=model,
            prompt_version=prompt_version,
            attempt_count=attempt_count,
        )

        summary["succeeded"] += 1

    logger.info("Enrichment summary: %s", summary)
    return summary