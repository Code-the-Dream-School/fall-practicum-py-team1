from importlib import import_module
from types import SimpleNamespace

import pytest

handler_module = import_module("pipeline.lambda_handler")


def test_lambda_handler_success(monkeypatch):
    """Test that the handler runs all pipeline stages successfully."""

    calls = []

    extracted_records = [{"city": "Fremont"}, {"city": "San Jose"}]
    raw_records = [{"city": "Fremont"}, {"city": "San Jose"}]
    locations = [{"city": "Fremont"}, {"city": "San Jose"}]
    gold_records = [{"city": "Fremont"}, {"city": "San Jose"}]

    fake_client = object()

    def fake_extract(kind):
        calls.append("extract")
        assert kind == "current"
        return extracted_records

    def fake_load_raw(records):
        calls.append("load_raw")
        assert records == extracted_records
        return 2

    def fake_create_supabase_client():
        calls.append("create_client")
        return fake_client

    def fake_fetch_raw_records(client):
        calls.append("fetch_raw")
        assert client is fake_client
        return raw_records

    def fake_fetch_locations(client):
        calls.append("fetch_locations")
        assert client is fake_client
        return locations

    def fake_transform(records, location_data):
        calls.append("transform")
        assert records == raw_records
        assert location_data == locations
        return gold_records

    def fake_load_gold(client, records):
        calls.append("load_gold")
        assert client is fake_client
        assert records == gold_records

    monkeypatch.setattr(handler_module, "extract", fake_extract)
    monkeypatch.setattr(handler_module, "load_raw_to_db", fake_load_raw)
    monkeypatch.setattr(
        handler_module, "create_supabase_client", fake_create_supabase_client
    )
    monkeypatch.setattr(
        handler_module, "fetch_raw_records", fake_fetch_raw_records
    )
    monkeypatch.setattr(
        handler_module, "fetch_locations", fake_fetch_locations
    )
    monkeypatch.setattr(handler_module, "transform", fake_transform)
    monkeypatch.setattr(handler_module, "load_gold", fake_load_gold)

    context = SimpleNamespace(aws_request_id="test-request-123")

    result = handler_module.lambda_handler({}, context)

    assert result["status"] == "success"
    assert result["request_id"] == "test-request-123"
    assert result["records_extracted"] == 2
    assert result["records_loaded"] == 2
    assert result["records_fetched_for_transform"] == 2
    assert result["records_transformed"] == 2
    assert result["records_submitted_to_gold"] == 2

    assert calls == [
        "extract",
        "load_raw",
        "create_client",
        "fetch_raw",
        "fetch_locations",
        "transform",
        "load_gold",
    ]


def test_lambda_handler_logs_failed_stage(monkeypatch, caplog):
    """Test that a stage failure is logged and the exception is re-raised."""

    def fake_extract(kind):
        return [{"city": "Fremont"}]

    def fake_load_raw(records):
        return 1

    def fake_create_supabase_client():
        return object()

    def fake_fetch_raw_records(client):
        return [{"city": "Fremont"}]

    def fake_fetch_locations(client):
        return [{"city": "Fremont"}]

    def fake_transform(records, locations):
        raise RuntimeError("Transformation failed")

    monkeypatch.setattr(handler_module, "extract", fake_extract)
    monkeypatch.setattr(handler_module, "load_raw_to_db", fake_load_raw)
    monkeypatch.setattr(
        handler_module, "create_supabase_client", fake_create_supabase_client
    )
    monkeypatch.setattr(
        handler_module, "fetch_raw_records", fake_fetch_raw_records
    )
    monkeypatch.setattr(
        handler_module, "fetch_locations", fake_fetch_locations
    )
    monkeypatch.setattr(handler_module, "transform", fake_transform)

    context = SimpleNamespace(aws_request_id="test-request-456")

    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError, match="Transformation failed"):
            handler_module.lambda_handler({}, context)

    assert "transformation" in caplog.text
    assert "Transformation failed" in caplog.text
