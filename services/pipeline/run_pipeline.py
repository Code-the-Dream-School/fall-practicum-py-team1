from core.io import create_supabase_client
from pipeline.extract.extract import extract
from pipeline.load.postgreSQL_schema_raw import load_records
from pipeline.transform.raw_to_gold import fetch_raw_records, fetch_locations, transform, load_gold
from datetime import datetime

def main():
    raise NotImplementedError
    # client = create_supabase_client()
    # raw_records = extract("history", datetime(2023, 1, 1).astimezone(), datetime(2024, 1, 1).astimezone())
    # load_records(raw_records, client)


if __name__ == "__main__":
    main()
