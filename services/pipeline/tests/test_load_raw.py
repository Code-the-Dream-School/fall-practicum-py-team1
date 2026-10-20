from unittest.mock import MagicMock, patch

import pytest

from pipeline.load.raw import RawLoadError, load_raw


def sample_record():
    return {
        "dt": 1792346400,
        "latitude": 38.6171,
        "longitude": -121.3283,
        "aqi": 2,
        "co": 139.58,
        "no": 0.0,
        "no2": 0.33,
        "o3": 91.18,
        "so2": 2.13,
        "pm2_5": 17.33,
        "pm10": 39.01,
        "nh3": 0.0,
    }


def test_load_raw_returns_zero_for_empty_records():
    with patch("pipeline.load.raw.psycopg.connect") as connect:
        assert load_raw([]) == 0

    connect.assert_not_called()


def test_load_raw_rejects_missing_fields():
    record = sample_record()
    del record["aqi"]

    with patch("pipeline.load.raw.psycopg.connect") as connect:
        with pytest.raises(ValueError, match="aqi"):
            load_raw([record])

    connect.assert_not_called()


def test_load_raw_upserts_records():
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_connection.__enter__.return_value = mock_connection
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

    with patch.dict("os.environ", {
        "SUPABASE_DB_HOST": "localhost",
        "SUPABASE_DB_NAME": "test_db",
        "SUPABASE_DB_USER": "test_user",
        "SUPABASE_DB_PASSWORD": "test_password",
    }), patch(
        "pipeline.load.raw.psycopg.connect",
        return_value=mock_connection,
    ):
        result = load_raw([sample_record()])

    assert result == 1
    mock_cursor.executemany.assert_called_once()

    sql = mock_cursor.executemany.call_args.args[0]
    assert "ON CONFLICT (dt, latitude, longitude)" in sql
    assert "DO UPDATE SET" in sql


def test_load_raw_reports_database_failure():
    with patch(
        "pipeline.load.raw.psycopg.connect",
        side_effect=OSError("Connection failed"),
    ):
        with pytest.raises(RawLoadError, match="Failed to write 1 raw record"):
            load_raw([sample_record()])


def test_load_raw_accepts_timestamp_string():
    record = sample_record()
    record["timestamp"] = "2026-10-18T12:00:00+00:00"
    del record["dt"]

    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connection.__enter__.return_value = mock_connection
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

    with patch.dict("os.environ", {
        "SUPABASE_DB_HOST": "localhost",
        "SUPABASE_DB_NAME": "test_db",
        "SUPABASE_DB_USER": "test_user",
        "SUPABASE_DB_PASSWORD": "test_password",
    }), patch(
        "pipeline.load.raw.psycopg.connect",
        return_value=mock_connection,
    ):
        assert load_raw([record]) == 1
    rows = mock_cursor.executemany.call_args.args[1]
    assert rows[0][0] == 1792324800
