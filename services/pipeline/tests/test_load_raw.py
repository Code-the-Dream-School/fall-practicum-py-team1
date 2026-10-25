from unittest.mock import MagicMock, patch

import pytest

from pipeline.extract.extract import RawRecord
from pipeline.load.raw import RawLoadError, load_raw


def sample_record(**overrides):
    values = {
        "city": "Carmichael",
        "lat": 38.6171,
        "lon": -121.3283,
        "dt": 1792346400,
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
    values.update(overrides)
    return RawRecord(**values)


def mock_database():
    connection = MagicMock()
    cursor = MagicMock()

    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor

    return connection, cursor


def test_load_raw_returns_zero_for_empty_records():
    with patch("pipeline.load.raw.psycopg.connect") as connect:
        assert load_raw([]) == 0

    connect.assert_not_called()


def test_load_raw_upserts_records():
    connection, cursor = mock_database()

    with patch.dict("os.environ", {
        "SUPABASE_DB_HOST": "localhost",
        "SUPABASE_DB_NAME": "test_db",
        "SUPABASE_DB_USER": "test_user",
        "SUPABASE_DB_PASSWORD": "test_password",
    }), patch(
        "pipeline.load.raw.psycopg.connect",
        return_value=connection,
    ):
        result = load_raw([sample_record()])

    assert result == 1
    cursor.executemany.assert_called_once()

    sql, rows = cursor.executemany.call_args.args
    assert "ON CONFLICT (dt, latitude, longitude)" in sql
    assert "DO UPDATE SET" in sql
    assert rows[0][:3] == (1792346400, 38.6171, -121.3283)


def test_load_raw_warns_for_missing_measurements(caplog):
    record = sample_record(aqi=None, co=None)

    connection, cursor = mock_database()

    with patch.dict("os.environ", {
        "SUPABASE_DB_HOST": "localhost",
        "SUPABASE_DB_NAME": "test_db",
        "SUPABASE_DB_USER": "test_user",
        "SUPABASE_DB_PASSWORD": "test_password",
    }), patch(
        "pipeline.load.raw.psycopg.connect",
        return_value=connection,
    ):
        assert load_raw([record]) == 1

    assert "aqi, co" in caplog.text

    rows = cursor.executemany.call_args.args[1]
    assert rows[0][3] is None
    assert rows[0][4] is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"dt": None},
        {"lat": None},
        {"lon": None},
    ],
)
def test_load_raw_rejects_missing_primary_key_values(overrides):
    with patch("pipeline.load.raw.psycopg.connect") as connect:
        with pytest.raises(ValueError, match="dt, lat, and lon"):
            load_raw([sample_record(**overrides)])

    connect.assert_not_called()


def test_load_raw_reports_database_failure():
    with patch.dict("os.environ", {
        "SUPABASE_DB_HOST": "localhost",
        "SUPABASE_DB_NAME": "test_db",
        "SUPABASE_DB_USER": "test_user",
        "SUPABASE_DB_PASSWORD": "test_password",
    }), patch(
        "pipeline.load.raw.psycopg.connect",
        side_effect=OSError("Connection failed"),
    ):
        with pytest.raises(RawLoadError, match="Failed to write 1 raw record"):
            load_raw([sample_record()])
