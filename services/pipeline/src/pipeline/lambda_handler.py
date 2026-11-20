import logging

from pipeline.extract.extract import extract
from pipeline.load.raw import load_raw as load_raw_to_db
from pipeline.transform.raw_to_gold import transform, load_gold

from core.io import (
    create_supabase_client,
    fetch_raw_records,
    fetch_locations,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    """AWS Lambda entry point for the City Air Tracker pipeline."""

    request_id = getattr(context, "aws_request_id", None)

    result = {
        "status": "failed",
        "request_id": request_id,
        "records_extracted": 0,
        "records_loaded": 0,
        "records_fetched_for_transform": 0,
        "records_transformed": 0,
        "records_submitted_to_gold": 0,
    }

    current_stage = "initialization"

    logger.info(
        "Starting City Air Tracker pipeline. Request ID: %s",
        request_id,
    )

    try:
        # 1. Extract data from OpenWeather
        current_stage = "extraction"
        logger.info("Starting extraction stage.")

        extracted_records = extract(kind="current")
        result["records_extracted"] = len(extracted_records)

        logger.info(
            "Extraction completed. Records extracted: %d",
            len(extracted_records),
        )

        # 2. Load extracted records into the Raw table
        current_stage = "raw_loading"
        logger.info("Starting raw loading stage.")

        loaded_count = load_raw_to_db(extracted_records)
        result["records_loaded"] = loaded_count

        logger.info(
            "Raw loading completed. Records loaded: %d",
            loaded_count,
        )

        # 3. Create Supabase client and fetch data
        current_stage = "supabase_data_fetch"
        logger.info("Creating Supabase client.")

        client = create_supabase_client()

        logger.info("Fetching raw records for transformation.")
        raw_records = fetch_raw_records(client)
        result["records_fetched_for_transform"] = len(raw_records)

        logger.info(
            "Fetched %d raw records.",
            len(raw_records),
        )

        logger.info("Fetching location records.")
        locations = fetch_locations(client)

        logger.info(
            "Fetched %d location records.",
            len(locations),
        )

        # 4. Transform raw records into Gold records
        current_stage = "transformation"
        logger.info("Starting transformation stage.")

        gold_records = transform(raw_records, locations)
        result["records_transformed"] = len(gold_records)

        logger.info(
            "Transformation completed. Records transformed: %d",
            len(gold_records),
        )

        # 5. Load transformed records into the Gold table
        current_stage = "gold_loading"
        logger.info("Starting Gold loading stage.")

        load_gold(client, gold_records)
        result["records_submitted_to_gold"] = len(gold_records)

        logger.info(
            "Gold loading completed. Records submitted: %d",
            len(gold_records),
        )

        result["status"] = "success"

        logger.info(
            "City Air Tracker pipeline completed successfully: %s",
            result,
        )

        return result

    except Exception as exc:
        result["failed_stage"] = current_stage
        result["error"] = str(exc)

        logger.exception(
            "Pipeline failed during stage '%s'. Result: %s",
            current_stage,
            result,
        )

        # Re-raise so AWS marks the Lambda invocation as failed.
        raise
