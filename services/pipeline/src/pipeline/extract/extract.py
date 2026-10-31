from datetime import datetime, timezone
from pipeline.extract.config import get_api_key, build_time_window
from typing import Literal, Callable
from dotenv import load_dotenv
from pipeline.extract.locations import load_locations
from pipeline.extract.fetch import fetch_air_pollution, validate_payload
from dataclasses import dataclass

import logging
from pipeline.log_run import save_run_record

import os
from supabase import create_client, Client

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
        warnings = []
        
        # Initialize Supabase client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if url and key:
            supabase: Client = create_client(url, key)
        else:
            supabase = None
            logger.warning("Supabase credentials not found in environment.")

        if start_ts and end_ts:
            start_ts, end_ts = build_time_window(start_ts, end_ts)
            
        for loc in locations:
            city = loc.get('city')
            lat = loc.get('lat')
            lon = loc.get('lon')
            
            # Format timestamps for cache database
            if isinstance(start_ts, int):
                cache_start = datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat()
            elif start_ts:
                cache_start = start_ts.isoformat()
            else:
                cache_start = "1970-01-01T00:00:00+00:00"
                
            if isinstance(end_ts, int):
                cache_end = datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat()
            elif end_ts:
                cache_end = end_ts.isoformat()
            else:
                cache_end = "2099-12-31T23:59:59+00:00"
            
            results = None
            
            # 1. Check the cache first
            if supabase:
                try:
                    cache_response = supabase.table("raw_air_quality_cache").select("raw_response") \
                        .eq("city", city) \
                        .eq("latitude", lat) \
                        .eq("longitude", lon) \
                        .eq("start_time", cache_start) \
                        .eq("end_time", cache_end) \
                        .execute()
                    
                    if cache_response.data:
                        logger.info(f"CACHE HIT: Returning cached data for {city}")
                        results = cache_response.data[0]["raw_response"]
                except Exception as e:
                    logger.warning(f"Cache check failed, proceeding to API call. Error: {e}")
            
            # 2. Cache Miss: Call the OpenWeather API
            if not results:
                logger.info(f"CACHE MISS: Fetching live API data for {city}")
                results = fetch_air_pollution(
                    kind=kind,
                    lat=lat,
                    lon=lon,
                    api_key=api_key,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    **kwarg
                )
                
                # 3. Store the new API response in the cache
                if supabase:
                    try:
                        cache_payload = {
                            "city": city,
                            "latitude": lat,
                            "longitude": lon,
                            "start_time": cache_start,
                            "end_time": cache_end,
                            "raw_response": results
                        }
                        supabase.table("raw_air_quality_cache").insert(cache_payload).execute()
                        logger.info(f"Successfully cached new data for {city}")
                    except Exception as e:
                         logger.warning(f"Failed to save to cache for {city}: {e}")

            warning = validator(results)
            warnings.extend(warning if warning else [])
            raw_records.extend(load_raw(city, results))            
            rows_processed = len(raw_records)
            
        status = "success"
        if warnings:
            logger.warning(warnings)
            error_message = f"Warning captured: {'\n'.join(warnings)}"
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
