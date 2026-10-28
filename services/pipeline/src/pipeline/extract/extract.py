from datetime import datetime, timezone
from pipeline.extract.config import get_api_key, build_time_window
from typing import Literal, Callable
from dotenv import load_dotenv
from pipeline.extract.locations import load_locations
from pipeline.extract.fetch import fetch_air_pollution, validate_payload
from dataclasses import dataclass, asdict

import logging
from pipeline.log_run import save_run_record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

@dataclass
class RawRecord:
    city: str
    lat: float
    lon: float
    dt: int
    aqi: int | None = None
    co: float | None = None
    no: float | None = None
    no2: float | None = None
    o3: float | None = None
    so2: float | None = None
    pm2_5: float | None = None
    pm10: float | None = None
    nh3: float | None = None

def load_raw(city: str, payload: dict) -> list[RawRecord]:
    """
    Load the given payload from a single city into RawRecord lists ready for upserting to database.

    Args:
        city: Name of the city, not a primary key.
        payload: The parsed JSON response from `fetch_air_pollution()`.
        warnings: List of warnings from `fetch_air_pollution()`, will depreciate in the next iteration.

    Returns:
        A list RawRecord dataclass ready for upserting into database.
    """
    raw_records = []
    coord = payload.get('coord', {})
    ls = payload.get('list', {})
    for entry in ls:
        main = entry.get('main', {})
        comp = entry.get('components', {})
        dt = entry.get('dt')
        raw_records.append(
            RawRecord(
                city=city,
                lat=coord.get('lat'),
                lon=coord.get('lon'),
                dt=dt,
                aqi=main.get('aqi'),
                co=comp.get('co'),
                no=comp.get('no'),
                no2=comp.get('no2'),
                o3=comp.get('o3'),
                so2=comp.get('so2'),
                pm2_5=comp.get('pm2_5'),
                pm10=comp.get('pm10'),
                nh3=comp.get('nh3')
            )
        )
    return raw_records

def extract(
        kind: Literal['current', 'history'], 
        start_ts: datetime | None = None, 
        end_ts: datetime | None = None, 
        validator: Callable[[dict], list[str]]=validate_payload, 
        **kwarg
        ) -> list[RawRecord]:
    """
    Full extract pipeline to fetch response from API to uploadable RawRecord class.

    Args:
        kind: 'current' or 'history' for different air pollution data.
        start_ts: Beginning date of parsing (datatime with timezone info) if 'history' is selected.
        end_ts: Ending date of parsing (datatime with timezone info) if 'history' is selected.
        **kwarg: Keyword args for `fetch_air_pollution()` function, see docstring for `fetch_air_pollution()` for more details.

    Returns:
        A list RawRecord dataclass ready for upserting into database.
    """
    # Logger setup
    logger = logging.getLogger(__name__)
    run_started = datetime.now(timezone.utc)
    status = "failed"          
    error_message = ""
    rows_processed = 0

    # Main function body
    try:
        raw_records = []
        load_dotenv()
        api_key = get_api_key()
        locations = load_locations()
        if start_ts and end_ts:
            start_ts, end_ts = build_time_window(start_ts, end_ts)
        for loc in locations:
            city = loc.get('city')
            lat = loc.get('lat')
            lon = loc.get('lon')
            results = fetch_air_pollution(
                kind=kind,
                lat=lat,
                lon=lon,
                api_key=api_key,
                start_ts=start_ts,
                end_ts=end_ts,
                **kwarg
            )

            logger = logging.getLogger(__name__)
            warnings = validator(results)
            status = "success"
            if warnings:
                logger.warning(warnings)
                error_message = f"Warning captured: {'\n'.join(warnings)}"
            raw_records.extend(load_raw(city, results))            
            rows_processed = len(raw_records)
        return raw_records
    except BaseException as e:
        error_message = str(e)
        logger.exception("extract() failed")
        raise
    finally:
        try:
            save_run_record(
                started_at=run_started,
                finished_at=datetime.now(timezone.utc),
                status=status,
                records_extracted=rows_processed,
                error_message=error_message,
            )
        except Exception:
            logger.exception("Could not save run record to database")

if __name__ == "__main__":
    load_dotenv()
    print("=" * 25)
    print("Test current call")
    print("=" * 25)
    raw_records = extract('current')
    for rec in raw_records:
        print(vars(rec))

    print("=" * 25)
    print("Test historic call")
    print("=" * 25)
    start_ts, end_ts = datetime.strptime("2026-01-01", "%Y-%m-%d").replace(tzinfo=timezone.utc), datetime.strptime("2026-01-31", "%Y-%m-%d").replace(tzinfo=timezone.utc)
    raw_records = extract('history', start_ts, end_ts)
    print(f"Historic record from {start_ts} to {end_ts}, {len(raw_records)} records extracted.")