import os
import logging
from core.config import RAW_TABLE, RAW_COLUMNS, GOLD_TABLE, GOLD_COLUMNS, LOCATIONS_TABLE

from supabase import create_client, Client
logger = logging.getLogger(__name__)

# --------------------------------------------------
# Supabase connection and data retrieval
# --------------------------------------------------

def create_supabase_client() -> Client:
    """Load system env keys for Supabase connection
    Returns:
        Initialized Supabase client
    
    Raises:    
        ValueError for missing SUPABASE_URL or SUPABASE_KEY in .env
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be configured in .env"
        )

    return create_client(url, key)


def fetch_all_rows(client: Client, table: str, columns: str="*", page_size=1000) -> list[dict]:
    """Fetch every row from a Supabase table using pagination.

    Supabase queries have a default 1,000-row limit. Pagination ensures
    all rows are fetched in batches of `page_size`.

    Args:
        client: An initialized Supabase `Client` used to run the queries.
        table: Name of the table to read from.
        columns: Columns to select, as a comma-separated string
            (e.g. `"id, name, created_at"`), default to `"*"` for all columns.
        page_size: Number of rows to request per batch. Should not exceed
            the Supabase row limit (1,000 by default).

    Returns:
        A list of tuples, one per row, with values ordered to match
        `columns`. The list is empty if the table has no rows.
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


def fetch_raw_records(client: Client, page_size: int=1000) -> list[tuple]:
    """Fetch every row from the raw table using pagination.

    Args:
        client: An initialized Supabase `Client` used to run the queries.
        page_size: Number of rows to request per batch. Should not exceed
            the Supabase row limit (1,000 by default).

    Returns:
        A list of tuples, one per row, with values ordered to RAW_COLUMNS.
        The list is empty if the table has no rows.
    """
    return fetch_all_rows(
        client,
        RAW_TABLE,
        ", ".join(RAW_COLUMNS),
        page_size=page_size
    )

def fetch_gold_records(client: Client, page_size: int=1000) -> list[tuple]:
    """Fetch every row from the gold table using pagination.

    Args:
        client: An initialized Supabase `Client` used to run the queries.
        page_size: Number of rows to request per batch. Should not exceed
            the Supabase row limit (1,000 by default).

    Returns:
        A list of tuples, one per row, with values ordered to GOLD_COLUMNS.
        The list is empty if the table has no rows.
    """
    return fetch_all_rows(
        client,
        GOLD_TABLE,
        ", ".join(GOLD_COLUMNS),
        page_size=page_size
    )


def fetch_locations(client: Client, page_size: int=1000) -> list[tuple]:
    """Fetch every row from the location table using pagination.
    
    Args:
        client: An initialized Supabase `Client` used to run the queries.
        page_size: Number of rows to request per batch. Should not exceed
            the Supabase row limit (1,000 by default).

    Returns:
        A list of tuples, one per row, with values ordered to "city,state,country,latitude,longitude,timezone".
        The list is empty if the table has no rows.
    """
    return fetch_all_rows(
        client,
        LOCATIONS_TABLE,
        "city,state,country,latitude,longitude,timezone",
    )
