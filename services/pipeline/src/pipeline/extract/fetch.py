import requests
import time

from services.pipeline.src.pipeline.errors import APIError, ERROR_MESSAGES, RETRY_STATUSES, MalformedPayloadError
from typing import Literal, Any, Callable
from datetime import datetime

def fetch_air_pollution(
        kind: Literal['current', 'history'], # choose between current or historic data
        lat: float, # lat for the coordinate of the city
        lon: float, # lon for the coordinate of the city
        api_key: str, # API key, NEVER HARDCODE THIS, use load_dotenv() or something similar
        start_ts: datetime | None = None, # Start timestamp for historic data
        end_ts: datetime | None = None, # End timestamp for historic data
        http_get: Callable[..., Any] = requests.get, # Use custom inject function for testing
        max_retries: int = 3, # Max number of retries, each time add a 2s delay
        base_delay: float = 1.0, # Start delay for retries
        max_delay: float = 10.0 # Maximum delay for retries
    ):
    """Fetching the air pollution API response"""
    params = {
                "lat": lat,
                "lon": lon,
                "appid": api_key,
            }

    if kind == 'current':
        base_url = "https://api.openweathermap.org/data/2.5/air_pollution"
    elif kind == 'history':
        base_url = "https://api.openweathermap.org/data/2.5/air_pollution/history"
        if not start_ts or not end_ts:
            raise ValueError("Missing start/end timestamp for historic data.")
        params["start"] = start_ts
        params["end"] = end_ts
    else:
        raise ValueError(f"Incorrect data kind ({kind}) to fetch, should be either 'current' or 'history'.")

    for attempt in range(max_retries + 1):
        try:
            resp = http_get(
                base_url,
                params=params,
                timeout=10
            )
            resp.raise_for_status()
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == max_retries:
                raise APIError(f"Network error: {e}") from e
            time.sleep(min(base_delay * 2 ** attempt, max_delay))
            continue

        status = resp.status_code

        if status == 200:
            return resp.json()

        if status in RETRY_STATUSES:
            if attempt == max_retries:
                raise APIError(f"Gave up after {max_retries} retries (HTTP {status}).")
            time.sleep(min(base_delay * 2 ** attempt, max_delay))
            continue

        raise APIError(ERROR_MESSAGES.get(status, f"Unexpected HTTP {status}."), status)

def validate_payload(payload: dict) -> list[str]:
    warnings = []
    if not payload:
        raise MalformedPayloadError("Empty payload")
    if not isinstance(payload, dict):
        raise MalformedPayloadError("Payload is not a dict")
    try:
        loc = payload['coord']
    except KeyError as e:
        raise MalformedPayloadError(f"Missing coordinate information: {e}")

    try:
        ls = payload['list']
    except KeyError as e:
        raise MalformedPayloadError(f"No `list` field in the payload: {e}")

    if len(ls) == 0:
        warnings.append("No air pollution data retrieved.")
    if not isinstance(ls, list):
        raise MalformedPayloadError(f"`list` of payload is not a list, it is {type(ls)} instead.")

    empty_entries = 0
    empty_dt = 0
    empty_main = 0
    empty_components = 0
    error_dts = {
        'main': [],
        'components': []
    }
    for l in ls:
        if not l:
            empty_entries += 1
        elif not isinstance(l, dict):
            raise MalformedPayloadError(f"Data in `list` of the payload is not a dict, problem data: {l}")
        else:
            if not l.get('dt'):
                empty_dt += 1
            if not l.get('main'):
                empty_main += 1
                error_dts['main'].append(l.get('dt'))
            if not l.get('components'):
                empty_components += 1
                error_dts['components'].append(l.get('dt'))

    if empty_entries > 0:
        warnings.append(f"{empty_entries} empty air data entries found.")
    if empty_dt > 0:
        warnings.append(f"{empty_dt} data missing dt value.")
    if empty_main > 0:
        warnings.append(f"{empty_main} data missing `main` field, at timestamps {error_dts['main']}.")
    if empty_components > 0:
        warnings.append(f"{empty_components} data missing `components` field, at timestamps {error_dts['components']}.")
        
    return warnings

if __name__ == "__main__":
    import os
    # from services.pipeline.tests.fixtures import http_get # importing the fake http_get() to test
    from dotenv import load_dotenv
    from datetime import timezone

    tests = ['current', 'history']
    start_ts = int(datetime.strptime('2023-01-01', "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime.strptime('2023-01-02', "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    lat, lon = 34.052235, -118.243683 # Los Angeles for test run
    load_dotenv()
    for test in tests:
        print("=" * 25)
        print(f"Test run for {test}")
        print("=" * 25)
        resp_json = fetch_air_pollution(
            kind=test,
            lat=lat,
            lon=lon,
            api_key=os.environ.get("OPENWEATHER_API_KEY"),
            start_ts=start_ts,
            end_ts=end_ts,
            # http_get=http_get # use the fake http_get for test
        )
        warnings = validate_payload(resp_json)
        record_cnt = len(resp_json.get('list'))
        print(f"{record_cnt} records retreived, sample response:")
        if record_cnt < 1:
            print(f"No record found for location at ({lat}, {lon})")
        print(resp_json['list'][0])
        print("Warnings:")
        print(warnings)        
        print()