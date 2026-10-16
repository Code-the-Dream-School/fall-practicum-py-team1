import requests
import time

from src.pipeline.errors import APIError, ERROR_MESSAGES, RETRY_STATUSES, MalformedPayloadError
from typing import Literal, Any, Callable
from datetime import datetime

def fetch_air_pollution(
        kind: Literal['current', 'history'], 
        lat: float, 
        lon: float, 
        api_key: str, 
        start_ts: datetime | None = None, 
        end_ts: datetime | None = None, 
        http_get: Callable[..., Any] = requests.get, 
        max_retries: int = 3, 
        base_delay: float = 1.0,
        max_delay: float = 10.0
    ):
    """Fetch the air pollution API response from OpenWeather.

    Args:
        kind: Choose between current or historic data.
        lat: Latitude of the city's coordinate.
        lon: Longitude of the city's coordinate.
        api_key: API key. Never hardcode this; use `load_dotenv()` or similar.
        start_ts: Start timestamp for historic data.
        end_ts: End timestamp for historic data.
        http_get: Injectable HTTP function, useful for testing.
        max_retries: Maximum number of retries.
        base_delay: Initial delay (seconds) between retries.
        max_delay: Maximum delay (seconds) between retries.

    Returns:
        The parsed API response in JSON.

    Raises:
        ValueError: If `kind` is `'history'` and `start_ts` or `end_ts` is missing.
        ValueError: If `kind` is not `current` or `history`
        APIError: Max connection retries reached and still not connecting
        APIError: Unexpected HTTP status
    """
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
    """Validate the structure of an OpenWeather air pollution API payload.

    Performs structural checks on the payload. Problems that make the payload
    unusable raise an exception. Problems that only affect some of the data are
    collected and returned as warnings, so the caller can decide how to handle
    them.

    Expected payload shape:
        - `coord`: coordinate information for the requested location.
        - `list`: a list of dict entries, each ideally containing `dt`,
          `main`, and `components`.

    Args:
        payload: The parsed JSON response from the air pollution API.

    Returns:
        A list of human-readable warning messages. The list is empty if no
        issues were found. Warnings are generated for:

        - An empty `list` (no air pollution data retrieved).
        - Empty entries in `list`.
        - Entries missing `dt`.
        - Entries missing `main` (reported with the affected timestamps).
        - Entries missing `components` (reported with the affected timestamps).

    Raises:
        MalformedPayloadError: If the payload is empty or not a dict.
        MalformedPayloadError: If the `coord` field is missing.
        MalformedPayloadError: If the `list` field is missing or is not a list.
        MalformedPayloadError: If any non-empty entry in `list` is not a dict.
    """
    warnings = []
    if not isinstance(payload, dict):
        raise MalformedPayloadError("Payload is not a dict")
    if not payload:
        raise MalformedPayloadError("Empty payload")
    
    if 'coord' not in payload:
        raise MalformedPayloadError(f"Missing coordinate information")

    try:
        ls = payload['list']
    except KeyError as e:
        raise MalformedPayloadError(f"No `list` field in the payload: {e}") from e

    if not isinstance(ls, list):
        raise MalformedPayloadError(f"`list` of payload is not a list, it is {type(ls)} instead.")
    if len(ls) == 0:
        warnings.append("No air pollution data retrieved.")
    

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