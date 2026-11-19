import argparse
from datetime import datetime
from prefect import flow, task, get_run_logger

# Import your team's actual pipeline stages
from pipeline.extract.extract import extract
from pipeline.transform.raw_to_gold import (
    transform as raw_to_gold_transform,
    create_supabase_client,
    fetch_locations
)
# Assuming the load function is named 'load_data' in the load module. 
# Update this import if your team named it differently (e.g., 'load_raw')
from pipeline.load import load_data 

@task(retries=3, retry_delay_seconds=10, name="Extract Raw Data")
def extract_task(kind: str, start_ts: datetime | None = None, end_ts: datetime | None = None):
    logger = get_run_logger()
    logger.info(f"Starting EXTRACT stage (Mode: {kind})")
    
    records = extract(kind=kind, start_ts=start_ts, end_ts=end_ts)
    
    logger.info(f"EXTRACT stage completed successfully. Extracted {len(records)} records.")
    return records

@task(name="Load Raw Data")
def load_task(records):
    logger = get_run_logger()
    logger.info("Starting LOAD stage")
    
    # Execute the real database load
    load_data(records)
    
    logger.info(f"LOAD stage completed successfully. {len(records)} records loaded.")
    return len(records)

@task(name="Transform Data")
def transform_task(records):
    logger = get_run_logger()
    logger.info("Starting TRANSFORM stage")
    
    # Fetch the locations reference data required by the transform function
    client = create_supabase_client()
    locations = fetch_locations(client)
    
    # Execute the real transformation
    gold_records = raw_to_gold_transform(records, locations)
    
    logger.info("TRANSFORM stage completed successfully.")
    return gold_records

@task(name="Enrich Data")
def enrich_task(gold_records):
    logger = get_run_logger()
    logger.info("Starting ENRICHMENT stage")
    
    # Placeholder: add the enrichment function in a future sprint
    logger.info("ENRICHMENT stage completed successfully.")
    return len(gold_records) if gold_records else 0

@flow(name="City Air Tracker ETL", log_prints=True)
def run_pipeline_flow(kind: str, start_ts: datetime | None = None, end_ts: datetime | None = None):
    logger = get_run_logger()
    logger.info(f"--- PIPELINE RUN STARTED: Mode={kind} ---")
    
    try:
        # Stage 1: Extract 
        raw_records = extract_task(kind, start_ts, end_ts)
        
        # Stage 2: Load 
        load_count = load_task(raw_records)
        
        # Stage 3: Transform 
        gold_records = transform_task(raw_records)
        
        # Stage 4: Enrich 
        enrich_count = enrich_task(gold_records)
        
        results = {
            "status": "success",
            "records_extracted": len(raw_records),
            "records_loaded": load_count,
            "records_enriched": enrich_count
        }
        logger.info(f"--- PIPELINE RUN COMPLETE --- Final Results: {results}")
        return results

    except Exception as e:
        logger.error(f"--- PIPELINE RUN FAILED --- Error encountered: {str(e)}")
        raise

def main():
    """CLI entry point executed by run_pipeline.py"""
    parser = argparse.ArgumentParser(description="Run the Air Quality ETL Pipeline")
    parser.add_argument("--mode", choices=["current", "history"], default="current", help="Extraction mode (current or history)")
    args = parser.parse_args()
    
    run_pipeline_flow(kind=args.mode)