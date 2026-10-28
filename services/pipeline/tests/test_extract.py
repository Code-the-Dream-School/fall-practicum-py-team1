from datetime import datetime, timezone
import pytest
import requests
import logging
from unittest.mock import Mock

import pipeline
from pipeline.extract.extract import load_raw, extract, RawRecord

def test_curret_load_raw(good_payload):
    coords = good_payload.get("coord")
    ls = good_payload.get("list")[0]
    aqi = ls.get("main").get("aqi")
    assert load_raw("Fremont", good_payload) == [RawRecord(
        "Fremont",
        coords.get("lat"),
        coords.get("lon"),
        ls.get("dt"),
        aqi,
        **ls["components"]
    )]

def test_history_load_raw(good_history_payload):
    raws = []
    coords = good_history_payload.get("coord")
    ls = good_history_payload.get("list")
    for l in ls:
        aqi = l.get("main").get("aqi")
        raws.append(
            RawRecord(
                "Fremont",
                coords.get("lat"),
                coords.get("lon"),
                l.get("dt"),
                aqi,
                **l["components"]
            )
        )
    assert load_raw("Fremont", good_history_payload) == raws

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
    assert results[0] == load_raw("Fremont", good_payload)[0]

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
    assert results == load_raw("Fremont", good_history_payload)

@pytest.mark.parametrize("fake_output, should_log", [
    (["temp missing"], True),
    ([], False),
    (None, False),
])
def test_extract_warning_logging(caplog, fake_output, should_log, scripted_get, monkeypatch, good_payload):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "fake")
    monkeypatch.setattr(
        "pipeline.extract.extract.load_locations",
        lambda: [{"city": "Fremont", "lat": 1, "lon": 2}],
    ) # Only get Fremont
    get = scripted_get(make_response(good_payload))
    # Patching the save_run_record to prevent actually logging to database
    monkeypatch.setattr(
        "pipeline.extract.extract.save_run_record",   
        lambda *args, **kwargs: None,
    )
    with caplog.at_level(logging.WARNING):
        extract("current", validator=lambda r: fake_output, http_get=get)
    assert ("WARNING" in caplog.text) == should_log
    assert (str(fake_output) in caplog.text) == should_log

# Testing the save_run_record
@pytest.mark.parametrize("kind, start_ts, end_ts", [
    ("current", None, None),
    ("history", datetime.strptime("2026-01-01", "%Y-%m-%d").replace(tzinfo=timezone.utc), datetime.strptime("2026-01-31", "%Y-%m-%d").replace(tzinfo=timezone.utc)),
])
def test_audit_row_on_success(monkeypatch, scripted_get, good_payload, good_history_payload, kind, start_ts, end_ts):
    saved = {}
    monkeypatch.setattr(pipeline.extract.extract, "save_run_record", lambda **r: saved.update(r))
    monkeypatch.setenv("OPENWEATHER_API_KEY", "fake")
    monkeypatch.setattr(
        "pipeline.extract.extract.load_locations",
        lambda: [{"city": "Fremont", "lat": 1, "lon": 2}],
    ) # Only get Fremont
    if kind == "current":
        get = scripted_get(make_response(good_payload))
    else:
        get = scripted_get(make_response(good_history_payload))
    extract(kind, start_ts=start_ts, end_ts=end_ts, http_get=get)

    assert saved["status"] == "success"
    assert saved["error_message"] == ""
    assert saved["records_extracted"] == (1 if kind == "current" else len(good_history_payload["list"]))

def test_audit_row_on_failure_and_error_propagates(monkeypatch, scripted_get, good_payload):
    saved = {}
    monkeypatch.setattr(pipeline.extract.extract, "save_run_record", lambda **r: saved.update(r))
    monkeypatch.setattr(
        "pipeline.extract.extract.load_locations",
        lambda: [{"city": "Fremont", "lat": 1, "lon": 2}],
    ) # Only get Fremont
    get = scripted_get(make_response(good_payload))

    def boom():
        raise RuntimeError("no key")
    monkeypatch.setattr(pipeline.extract.extract, "get_api_key", boom)

    with pytest.raises(RuntimeError):          # still re-raised
        extract('current', http_get=get)

    assert saved["status"] == "failed"
    assert "no key" in saved["error_message"]