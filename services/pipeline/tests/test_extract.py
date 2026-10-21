from datetime import datetime, timezone
import pytest
import requests
from unittest.mock import Mock

from pipeline.extract.extract import load_raw, extract, RawRecord

def test_curret_load_raw(good_payload):
    coords = good_payload.get("coord")
    ls = good_payload.get("list")[0]
    aqi = ls.get("main").get("aqi")
    raw = load_raw("Fremont", good_payload, warnings=["This is a warning"])
    current_time = datetime.now()
    # raw[0].ingested_at = current_time
    assert load_raw("Fremont", good_payload, warnings=["This is a warning"]) == [RawRecord(
        "Fremont",
        coords.get("lat"),
        coords.get("lon"),
        ls.get("dt"),
        aqi,
        **ls["components"],
        # ingested_at=current_time,
        # warnings=["This is a warning"]
    )]

def test_history_load_raw(good_history_payload):
    raws = []
    coords = good_history_payload.get("coord")
    ls = good_history_payload.get("list")
    current_time = datetime.now()
    for l in ls:
        aqi = l.get("main").get("aqi")
        raw = load_raw("Fremont", good_history_payload, warnings=["This is a warning"])
        # raw[0].ingested_at = current_time
        raws.append(
            RawRecord(
                "Fremont",
                coords.get("lat"),
                coords.get("lon"),
                l.get("dt"),
                aqi,
                **l["components"],
                # ingested_at=current_time,
                # warnings=["This is a warning"]
            )
        )
    assert load_raw("Fremont", good_history_payload, warnings=["This is a warning"]) == raws

def make_response(json_data=None, status=200):
    resp = Mock()
    resp.status_code = status
    resp.json.return_value = json_data if json_data is not None else {}
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(str(status))
    return resp

def test_extract_current(good_payload, scripted_get, monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "fake")
    monkeypatch.setattr(
        "pipeline.extract.extract.load_locations",
        lambda: [{"city": "Fremont", "lat": 1, "lon": 2}],
    ) # Only get Fremont
    get = scripted_get(make_response(good_payload))
    results = extract('current', http_get=get)
    assert len(results) == 1
    assert results[0] == load_raw("Fremont", good_payload, warnings=[])[0]

def test_extract_history(good_history_payload, scripted_get, monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "fake")
    monkeypatch.setattr(
        "pipeline.extract.extract.load_locations",
        lambda: [{"city": "Fremont", "lat": 1, "lon": 2}],
    ) # Only get Fremont
    get = scripted_get(make_response(good_history_payload))
    results = extract('history', 
                      http_get=get, 
                      start_ts=datetime.strptime("2026-01-01", "%Y-%m-%d").astimezone(timezone.utc),
                      end_ts=datetime.strptime("2026-01-01", "%Y-%m-%d").astimezone(timezone.utc))
    assert len(results) == 25
    assert results == load_raw("Fremont", good_history_payload, warnings=[])