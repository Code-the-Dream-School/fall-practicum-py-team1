import pytest
import requests
import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock

from pipeline.extract.fetch import fetch_air_pollution, validate_payload
from pipeline.errors import MalformedPayloadError, APIError, RETRY_STATUSES

def make_response(json_data=None, status=200):
    resp = Mock()
    resp.status_code = status
    resp.json.return_value = json_data if json_data is not None else {}
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(str(status))
    return resp

# Testing fetch_air_pollution()
def test_current_returns_json_and_sends_expected_params(scripted_get, good_payload):
    get = scripted_get(make_response(good_payload))

    result = fetch_air_pollution("current", 2, 1, api_key="KEY", http_get=get)

    assert result == (good_payload, [])
    get.assert_called_once()
    _, kwargs = get.call_args 
    assert kwargs["params"]["lat"] == 2
    assert kwargs["params"]["lon"] == 1
    assert kwargs["params"]["appid"] == "KEY"

def test_history_without_timestamps_raises(scripted_get):
    get = scripted_get()
    with pytest.raises(ValueError, match="Missing start/end timestamp"):
        fetch_air_pollution("history", 2, 1, "KEY", http_get=get)
    get.assert_not_called()

def test_wrong_kind_raises(scripted_get):
    get = scripted_get()
    with pytest.raises(ValueError, match="Incorrect data kind"):
        fetch_air_pollution("kinder", 2, 1, "KEY", http_get=get)
    get.assert_not_called()

def test_retries_then_succeeds(scripted_get, good_payload, sleeps):
    get = scripted_get(
        requests.ConnectionError("boom"),
        make_response({}, status=500),
        make_response(good_payload),
    )

    result = fetch_air_pollution("current", 1.0, 2.0, "KEY", http_get=get, max_retries=3)

    assert result == (good_payload, [])
    assert get.call_count == 3
    assert len(sleeps) == 2          # slept between attempts only

def test_retries_then_fail(scripted_get, sleeps):
    get = scripted_get(
        requests.ConnectionError("boom"),
        requests.Timeout(),
        make_response({}, status=500),
        make_response({}, status=429),
    )

    with pytest.raises(APIError, match="retries"):
        fetch_air_pollution("current", 1.0, 2.0, "KEY", http_get=get, max_retries=3)

def test_unexpected_http_error(scripted_get):
    get = scripted_get(make_response({}, status=418))
    with pytest.raises(APIError, match="Unexpected"):
        fetch_air_pollution("current", 1.0, 2.0, "KEY", http_get=get)

@pytest.mark.parametrize("status", sorted(RETRY_STATUSES))
def test_retries_on_each_retryable_status(scripted_get, good_payload, sleeps, status): # sleeps for overwriting the actual sleep with calls.sleep
    get = scripted_get(make_response({}, status=status), make_response(good_payload))

    result = fetch_air_pollution("current", 1.0, 2.0, "KEY", http_get=get, max_retries=3)

    assert result == (good_payload, [])
    assert get.call_count == 2

def test_backoff_is_capped(scripted_get, sleeps):
    get = scripted_get(*[requests.Timeout()] * 6)

    with pytest.raises(APIError, match="Network error"):
        fetch_air_pollution(
            "current", 1.0, 2.0, "KEY", http_get=get,
            max_retries=5, base_delay=1.0, max_delay=3.0,
        )

    assert max(sleeps) <= 3.0
    assert sleeps == sorted(sleeps)   # non-decreasing

# Testing validate_payload()
def test_correct_payload(good_payload):
    warnings = validate_payload(good_payload)
    assert len(warnings) == 0

@pytest.mark.parametrize("bad_payload", [["test"], [], "text", 42, None])
def test_incorrect_payload_type(bad_payload):
    with pytest.raises(MalformedPayloadError, match="not a dict"):
        validate_payload(bad_payload)

def test_empty_payload():
    with pytest.raises(MalformedPayloadError, match="Empty payload"):
        validate_payload({})

def test_missing_coord(good_payload):
    del good_payload["coord"]
    with pytest.raises(MalformedPayloadError, match="Missing coord"):
            validate_payload(good_payload)

def test_missing_list(good_payload):
    del good_payload["list"]
    with pytest.raises(MalformedPayloadError, match="No `list`"):
        validate_payload(good_payload)

def test_list_wrong_type(good_payload):
    good_payload["list"] = "This is a string"
    with pytest.raises(MalformedPayloadError, match="str"):
        validate_payload(good_payload)

def test_list_empty(good_payload):
    good_payload["list"] = []
    assert "No air pollution data retrieved." in validate_payload(good_payload)

def test_list_contains_non_dict(good_payload):
    good_payload["list"] = [{}, "Not a dict", {"a": "b"}]
    with pytest.raises(MalformedPayloadError, match="not a dict"):
        validate_payload(good_payload)

# Testing the warnings
def make_entry(dt=1, main=True, components=True):
    entry = {}
    if dt is not None:
        entry["dt"] = dt
    if main is not None:
        entry["main"] = {"aqi": 1}
    if components is not None:
        entry["components"] = {"co": 0.5}
    return entry


def test_valid_payload_has_no_warnings(good_payload):
    assert validate_payload(good_payload) == []


def test_empty_list_warns(good_payload):
    good_payload["list"] = []
    assert validate_payload(good_payload) == ["No air pollution data retrieved."]


def test_empty_entries_are_counted(good_payload):
    good_payload["list"] = [{}, {}, {}]
    assert validate_payload(good_payload) == ["3 empty air data entries found."]


def test_missing_dt(good_payload):
    good_payload["list"] = [make_entry(dt=None)]
    with pytest.raises(MalformedPayloadError, match="missing timestamp"):
        validate_payload(good_payload)


def test_missing_main_reports_timestamp(good_payload):
    good_payload["list"] = [make_entry(dt=123, main=None)]
    assert validate_payload(good_payload) == [
        "1 data missing `main` field, at timestamps [123]."
    ]


def test_missing_components_reports_timestamp(good_payload):
    good_payload["list"] = [make_entry(dt=456, components=None)]
    assert validate_payload(good_payload) == [
        "1 data missing `components` field, at timestamps [456]."
    ]


def test_multiple_missing_main_lists_all_timestamps(good_payload):
    good_payload["list"] = [
        make_entry(dt=1, main=None),
        make_entry(dt=2),                 # fine, shouldn't be reported
        make_entry(dt=3, main=None),
    ]
    assert validate_payload(good_payload) == [
        "2 data missing `main` field, at timestamps [1, 3]."
    ]


@pytest.mark.parametrize("falsy_value", [None, {}])
def test_falsy_main_counts_as_missing(good_payload, falsy_value):
    good_payload["list"][0]["main"] = falsy_value
    warnings = validate_payload(good_payload)
    assert len(warnings) == 1
    assert "`main`" in warnings[0]

def test_entry_missing_everything_but_nonempty(good_payload):
    good_payload["list"] = [{"extra": 1, "dt": 1}]   # non-empty dict, no expected keys
    assert validate_payload(good_payload) == [
        "1 data missing `main` field, at timestamps [1].",
        "1 data missing `components` field, at timestamps [1].",
    ]


def test_all_warning_types_together_in_order(good_payload):
    good_payload["list"] = [
        {},                                      # empty entry
        make_entry(dt=10, main=None),            # missing main
        make_entry(dt=20, components=None),      # missing components
    ]
    assert validate_payload(good_payload) == [
        "1 empty air data entries found.",
        "1 data missing `main` field, at timestamps [10].",
        "1 data missing `components` field, at timestamps [20].",
    ]