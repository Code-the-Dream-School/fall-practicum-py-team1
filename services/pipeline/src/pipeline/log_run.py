import os
from datetime import datetime
from typing import Literal
from dotenv import load_dotenv
from supabase import create_client

LOG_TABLE = "pipeline_runs"

def create_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be configured in .env"
        )

    return create_client(url, key)


def save_run_record(
        started_at: datetime | str,
        finished_at: datetime | str,
        status: Literal["success", "failed"],
        records_extracted: int=0,
        records_loaded: int=0,
        records_transformed: int=0,
        error_message: str=""
):
    if isinstance(started_at, datetime):
        started_at = started_at.isoformat()
    if isinstance(finished_at, datetime):
        finished_at = finished_at.isoformat()
    load_dotenv()
    client = create_supabase_client()
    client.table(LOG_TABLE).insert(
        {
            "started_at": started_at,
            "finished_at": finished_at,
            "status": status,
            "records_extracted": records_extracted,
            "records_loaded": records_loaded,
            "records_transformed": records_transformed,
            "error_message": error_message
        }
    ).execute()