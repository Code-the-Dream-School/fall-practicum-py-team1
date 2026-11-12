
import sys
import importlib.util
from pathlib import Path
from unittest.mock import Mock, call

import pandas as pd
import pytest


"""
TEST SUITE: AIR POLLUTION DASHBOARD

This test file verifies the main functionality of the
City Air Tracker dashboard.

Tests cover:

1. Gold Layer data retrieval from Supabase.
2. Handling empty database responses.
3. Data pagination when retrieving large datasets.
4. Date range filtering and boundary conditions.
5. Dashboard KPI and pollution metric calculations.
6. Handling missing and invalid numeric values.
7. Daily enrichment matching using city coordinates and dates.
8. Selecting the enrichment record closest to 12 PM UTC.
9. Preferring later timestamps when time differences are equal.
10. Handling missing, failed, or invalid enrichment records.
11. Ensuring enrichment records only match the correct day.
12. Ensuring original DataFrames are not modified.

All database interactions are mocked to avoid
depending on a live Supabase connection.

Run tests using:
pytest services/pipeline/tests/test_dashboard.py -v
"""





# ---------------------------------------------------------
# IMPORT PROJECT MODULE
# ---------------------------------------------------------

PIPELINE_SRC = Path(__file__).resolve().parents[1] / "src"

if str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))

DASHBOARD_PATH = (
    PIPELINE_SRC / "pipeline" / "orchestration" / "dashboard.py"
)

spec = importlib.util.spec_from_file_location(
    "dashboard",
    DASHBOARD_PATH
)

dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


# ---------------------------------------------------------
# FIXTURE: SAMPLE GOLD LAYER DATA
# ---------------------------------------------------------

@pytest.fixture
def sample_gold_data():
    """Provide realistic sample Gold Layer records."""

    return [
        {
            "city": "London",
            "timestamp": "2026-11-01T10:00:00Z",
            "aqi": 45,
            "category": "Good",
            "co": 200,
            "no": 5,
            "no2": 15,
            "o3": 30,
            "so2": 4,
            "pm2_5": 10,
            "pm10": 20,
            "nh3": 2,
            "aqi_rolling_avg": 42,
            "daily_max": 55,
            "daily_min": 30,
            "daily_range": 25,
            "pollution_score": 30
        },
        {
            "city": "Paris",
            "timestamp": "2026-11-02T10:00:00Z",
            "aqi": 60,
            "category": "Moderate",
            "co": 250,
            "no": 7,
            "no2": 20,
            "o3": 40,
            "so2": 5,
            "pm2_5": 15,
            "pm10": 25,
            "nh3": 3,
            "aqi_rolling_avg": 58,
            "daily_max": 70,
            "daily_min": 45,
            "daily_range": 25,
            "pollution_score": 40
        }
    ]



# ---------------------------------------------------------
# FIXTURE: CLEAR STREAMLIT CACHE BEFORE EACH TEST
# ---------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_streamlit_cache():
    """Clear Streamlit cached data before every test."""

    dashboard.get_gold_data.clear()
    dashboard.get_air_pollution_enrichment.clear()
    dashboard.match_daily_enrichment.clear()

    yield

    dashboard.get_gold_data.clear()
    dashboard.get_air_pollution_enrichment.clear()
    dashboard.match_daily_enrichment.clear()


# ---------------------------------------------------------
# HELPER: MOCK SUPABASE
# ---------------------------------------------------------

def mock_supabase(monkeypatch, responses):
    """Create a fake Supabase client for testing."""

    mock_client = Mock()

    execute_mock = (
        mock_client.table.return_value
        .select.return_value
        .range.return_value
        .execute
    )

    execute_mock.side_effect = responses

    monkeypatch.setattr(
        dashboard,
        "load_dotenv",
        Mock()
    )

    monkeypatch.setattr(
        dashboard.os,
        "getenv",
        lambda key: "fake_value"
    )

    monkeypatch.setattr(
        dashboard,
        "create_client",
        Mock(return_value=mock_client)
    )

    return mock_client, execute_mock


# ---------------------------------------------------------
# TEST 1: DATA RETRIEVAL
# ---------------------------------------------------------

def test_get_gold_data(monkeypatch, sample_gold_data):
    """Test successful retrieval of Gold Layer records."""

    # ARRANGE
    mock_response = Mock()
    mock_response.data = sample_gold_data

    mock_supabase(monkeypatch, [mock_response])

    # ACT
    result = dashboard.get_gold_data()

    # ASSERT
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2

    assert result["city"].tolist() == [
        "London",
        "Paris"
    ]

    assert "timestamp" in result.columns
    assert "pollution_score" in result.columns
    assert "pm2_5" in result.columns

    assert result["aqi"].tolist() == [45, 60]


# ---------------------------------------------------------
# TEST 2: EMPTY RESULTS
# ---------------------------------------------------------

def test_get_gold_data_empty(monkeypatch):
    """Test handling of empty Supabase results."""

    # ARRANGE
    mock_response = Mock()
    mock_response.data = []

    mock_supabase(monkeypatch, [mock_response])

    mock_warning = Mock()

    monkeypatch.setattr(
        dashboard.st,
        "warning",
        mock_warning
    )

    # ACT
    result = dashboard.get_gold_data()

    # ASSERT
    assert isinstance(result, pd.DataFrame)
    assert result.empty

    mock_warning.assert_called_once_with(
        "No data found in the gold table."
    )


# ---------------------------------------------------------
# TEST 3: PAGINATION
# ---------------------------------------------------------

def test_get_gold_data_pagination(monkeypatch):
    """Test that all records are retrieved using pagination."""

    # ARRANGE

    batch1 = [
        {"city": "London", "aqi": i}
        for i in range(1000)
    ]

    batch2 = [
        {"city": "Paris", "aqi": i}
        for i in range(1000)
    ]

    batch3 = [
        {"city": "Berlin", "aqi": i}
        for i in range(500)
    ]

    responses = []

    for batch in [batch1, batch2, batch3]:
        response = Mock()
        response.data = batch
        responses.append(response)

    mock_client, execute_mock = mock_supabase(
        monkeypatch,
        responses
    )

    # ACT
    result = dashboard.get_gold_data()

    # ASSERT
    assert len(result) == 2500

    assert execute_mock.call_count == 3

    range_mock = (
        mock_client.table.return_value
        .select.return_value
        .range
    )

    assert range_mock.call_args_list == [
        call(0, 999),
        call(1000, 1999),
        call(2000, 2999)
    ]


# ---------------------------------------------------------
# HELPER: PREPARE DATA FOR DATE FILTERING
# ---------------------------------------------------------

def prepare_datetime_data(sample_gold_data):
    """Convert sample timestamps into Pandas datetime values."""

    df = pd.DataFrame(sample_gold_data)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True
    )

    return df


# ---------------------------------------------------------
# TEST 4: DATE FILTERING
# ---------------------------------------------------------

def test_date_filtering(sample_gold_data):
    """Test that records inside the selected date range are returned."""

    # ARRANGE
    df = prepare_datetime_data(sample_gold_data)

    start_date = pd.Timestamp("2026-11-01").date()
    end_date = pd.Timestamp("2026-11-01").date()

    # ACT
    result = dashboard.filter_by_date_range(
        df,
        (start_date, end_date)
    )

    # ASSERT
    assert len(result) == 1
    assert result["city"].tolist() == ["London"]
    assert result["aqi"].tolist() == [45]


# ---------------------------------------------------------
# TEST 5: EXCLUDE RECORDS OUTSIDE DATE RANGE
# ---------------------------------------------------------

def test_date_filtering_excludes_outside_dates(sample_gold_data):
    """Test that records outside the selected range are excluded."""

    # ARRANGE
    df = prepare_datetime_data(sample_gold_data)

    start_date = pd.Timestamp("2026-11-03").date()
    end_date = pd.Timestamp("2026-11-04").date()

    # ACT
    result = dashboard.filter_by_date_range(
        df,
        (start_date, end_date)
    )

    # ASSERT
    assert result.empty
    assert len(result) == 0


# ---------------------------------------------------------
# TEST 6: DATE RANGE BOUNDARIES
# ---------------------------------------------------------

def test_date_filtering_includes_boundary_dates(sample_gold_data):
    """Test that both start and end dates are included."""

    # ARRANGE
    df = prepare_datetime_data(sample_gold_data)

    start_date = pd.Timestamp("2026-11-01").date()
    end_date = pd.Timestamp("2026-11-02").date()

    # ACT
    result = dashboard.filter_by_date_range(
        df,
        (start_date, end_date)
    )

    # ASSERT
    assert len(result) == 2

    assert result["city"].tolist() == [
        "London",
        "Paris"
    ]

    assert result["aqi"].tolist() == [45, 60]




# ---------------------------------------------------------
# TEST 7: DASHBOARD METRICS
# ---------------------------------------------------------

def test_calculate_dashboard_metrics(sample_gold_data):
    """Test all dashboard metrics using sample Gold Layer data."""

    # ARRANGE
    df = pd.DataFrame(sample_gold_data)

    # ACT
    result = dashboard.calculate_dashboard_metrics(df)

    # ASSERT
    assert result["average_aqi"] == 52.5
    assert result["maximum_aqi"] == 60

    assert result["average_pm25"] == 12.5
    assert result["average_pm10"] == 22.5
    assert result["average_o3"] == 35

    assert result["average_pollution_score"] == 35

    assert result["total_records"] == 2
    assert result["monitored_cities"] == 2


# ---------------------------------------------------------
# TEST 8: DASHBOARD METRICS WITH ONE CITY
# ---------------------------------------------------------

def test_dashboard_metrics_single_city(sample_gold_data):
    """Test metrics when records belong to one city."""

    # ARRANGE
    df = pd.DataFrame(sample_gold_data)

    df = df[df["city"] == "London"]

    # ACT
    result = dashboard.calculate_dashboard_metrics(df)

    # ASSERT
    assert result["average_aqi"] == 45
    assert result["maximum_aqi"] == 45
    assert result["total_records"] == 1
    assert result["monitored_cities"] == 1


# ---------------------------------------------------------
# TEST 9: DASHBOARD METRICS WITH MISSING VALUES
# ---------------------------------------------------------

def test_dashboard_metrics_missing_values(sample_gold_data):
    """Test metrics when some pollutant values are missing."""

    # ARRANGE
    df = pd.DataFrame(sample_gold_data)

    df.loc[0, "aqi"] = None
    df.loc[1, "pm2_5"] = None

    # ACT
    result = dashboard.calculate_dashboard_metrics(df)

    # ASSERT
    assert result["average_aqi"] == 60
    assert result["average_pm25"] == 10
    assert result["total_records"] == 2
    assert result["monitored_cities"] == 2


#
# ---------------------------------------------------------
# TEST 10: DASHBOARD METRICS WITH INVALID VALUES
# ---------------------------------------------------------

def test_dashboard_metrics_invalid_values(sample_gold_data):
    """Test metrics when numeric columns contain invalid values."""

    # ARRANGE
    df = pd.DataFrame(sample_gold_data)

    # Convert the column to object so it can hold text values.
    df["aqi"] = df["aqi"].astype(object)

    # Insert an invalid AQI value.
    df.loc[0, "aqi"] = "invalid"

    # Convert invalid values into NaN.
    df["aqi"] = pd.to_numeric(
        df["aqi"],
        errors="coerce"
    )

    # ACT
    result = dashboard.calculate_dashboard_metrics(df)

    # ASSERT
    assert result["average_aqi"] == 60
    assert result["maximum_aqi"] == 60


# ---------------------------------------------------------
# TEST 11–18: DAILY ENRICHMENT MATCHING
# ---------------------------------------------------------

@pytest.fixture
def sample_enrichment_data():
    """Provide sample successful and unsuccessful AI enrichment records."""

    return pd.DataFrame([
        {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": "2026-11-01T10:00:00Z",
            "status": "success",
            "result": {
                "summary": "Good air quality.",
                "recommendation": "Outdoor activities are suitable.",
                "pollutant_analysis": "Pollutant levels are low."
            }
        },
        {
            "latitude": 48.8566,
            "longitude": 2.3522,
            "timestamp": "2026-11-02T11:30:00Z",
            "status": "success",
            "result": {
                "summary": "Moderate air quality.",
                "recommendation": "Limit prolonged outdoor activity.",
                "pollutant_analysis": "PM2.5 levels are elevated."
            }
        },
        {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": "2026-11-01T12:00:00Z",
            "status": "failed",
            "result": None
        }
    ])


@pytest.fixture
def sample_trend_data():
    """Provide daily AQI records for enrichment matching."""

    return pd.DataFrame([
        {
            "city": "London",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": "2026-11-01T00:00:00Z",
            "aqi": 45
        },
        {
            "city": "Paris",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "timestamp": "2026-11-02T00:00:00Z",
            "aqi": 60
        },
        {
            "city": "New York",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": "2026-11-01T00:00:00Z",
            "aqi": 55
        }
    ])


# ---------------------------------------------------------
# TEST 11: SUCCESSFUL ENRICHMENT MATCHING
# ---------------------------------------------------------

def test_match_daily_enrichment_success(
    sample_trend_data,
    sample_enrichment_data
):
    """Test successful matching of enrichment records."""

    result = dashboard.match_daily_enrichment(
        sample_trend_data,
        sample_enrichment_data
    )

    london = result[result["city"] == "London"].iloc[0]

    assert london["enrichment_status"] == "Enrichment available"
    assert london["summary"] == "Good air quality."
    assert london["recommendation"] == (
        "Outdoor activities are suitable."
    )
    assert london["pollutant_analysis"] == (
        "Pollutant levels are low."
    )


# ---------------------------------------------------------
# TEST 12: NO ENRICHMENT RECORD AVAILABLE
# ---------------------------------------------------------

def test_match_daily_enrichment_no_records(
    sample_trend_data
):
    """Test that missing enrichment is reported correctly."""

    empty_enrichment = pd.DataFrame(columns=[
        "latitude",
        "longitude",
        "timestamp",
        "status",
        "result"
    ])

    result = dashboard.match_daily_enrichment(
        sample_trend_data,
        empty_enrichment
    )

    assert (
        result["enrichment_status"]
        == "No enrichment records available"
    ).all()

    assert result["summary"].isna().all()
    assert result["recommendation"].isna().all()
    assert result["pollutant_analysis"].isna().all()


# ---------------------------------------------------------
# TEST 13: FAILED ENRICHMENT RECORDS ARE IGNORED
# ---------------------------------------------------------

def test_match_daily_enrichment_ignores_failed_records(
    sample_trend_data
):
    """Test that failed enrichment records are not selected."""

    failed_data = pd.DataFrame([
        {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": "2026-11-01T12:00:00Z",
            "status": "failed",
            "result": None
        }
    ])

    result = dashboard.match_daily_enrichment(
        sample_trend_data,
        failed_data
    )

    london = result[result["city"] == "London"].iloc[0]

    assert london["enrichment_status"] == (
        "No enrichment records available"
    )

    assert pd.isna(london["summary"])


# ---------------------------------------------------------
# TEST 14: CLOSEST TIMESTAMP TO NOON
# ---------------------------------------------------------

def test_match_daily_enrichment_closest_to_noon(
    sample_trend_data
):
    """Test that the record closest to 12 PM UTC is selected."""

    enrichment = pd.DataFrame([
        {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": "2026-11-01T09:00:00Z",
            "status": "success",
            "result": {"summary": "Morning record"}
        },
        {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": "2026-11-01T11:50:00Z",
            "status": "success",
            "result": {"summary": "Closest record"}
        },
        {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": "2026-11-01T15:00:00Z",
            "status": "success",
            "result": {"summary": "Afternoon record"}
        }
    ])

    result = dashboard.match_daily_enrichment(
        sample_trend_data,
        enrichment
    )

    london = result[result["city"] == "London"].iloc[0]

    assert london["summary"] == "Closest record"


# ---------------------------------------------------------
# TEST 15: LATER TIMESTAMP WINS WHEN EQUALLY CLOSE
# ---------------------------------------------------------

def test_match_daily_enrichment_later_timestamp_wins(
    sample_trend_data
):
    """Test that later timestamp wins when distances are equal."""

    enrichment = pd.DataFrame([
        {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": "2026-11-01T11:00:00Z",
            "status": "success",
            "result": {"summary": "Earlier record"}
        },
        {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": "2026-11-01T13:00:00Z",
            "status": "success",
            "result": {"summary": "Later record"}
        }
    ])

    result = dashboard.match_daily_enrichment(
        sample_trend_data,
        enrichment
    )

    london = result[result["city"] == "London"].iloc[0]

    assert london["summary"] == "Later record"


# ---------------------------------------------------------
# TEST 16: DIFFERENT DATES MUST NOT MATCH
# ---------------------------------------------------------

def test_match_daily_enrichment_same_day_only(
    sample_trend_data
):
    """Test that enrichment from another date is ignored."""

    enrichment = pd.DataFrame([
        {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": "2026-11-02T12:00:00Z",
            "status": "success",
            "result": {"summary": "Different day"}
        }
    ])

    result = dashboard.match_daily_enrichment(
        sample_trend_data,
        enrichment
    )

    london = result[result["city"] == "London"].iloc[0]

    assert london["enrichment_status"] == (
        "No enrichment records available"
    )

    assert pd.isna(london["summary"])


# ---------------------------------------------------------
# TEST 17: INVALID TIMESTAMPS ARE IGNORED
# ---------------------------------------------------------

def test_match_daily_enrichment_invalid_timestamps(
    sample_trend_data
):
    """Test that invalid enrichment timestamps are ignored."""

    enrichment = pd.DataFrame([
        {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": "invalid_timestamp",
            "status": "success",
            "result": {"summary": "Invalid timestamp"}
        }
    ])

    result = dashboard.match_daily_enrichment(
        sample_trend_data,
        enrichment
    )

    london = result[result["city"] == "London"].iloc[0]

    assert london["enrichment_status"] == (
        "No enrichment records available"
    )


# ---------------------------------------------------------
# TEST 18: ORIGINAL DATAFRAMES REMAIN UNCHANGED
# ---------------------------------------------------------

def test_match_daily_enrichment_does_not_modify_original(
    sample_trend_data,
    sample_enrichment_data
):
    """Test that the matching function preserves input DataFrames."""

    original_trend = sample_trend_data.copy(deep=True)
    original_enrichment = sample_enrichment_data.copy(deep=True)

    dashboard.match_daily_enrichment(
        sample_trend_data,
        sample_enrichment_data
    )

    pd.testing.assert_frame_equal(
        sample_trend_data,
        original_trend
    )

    pd.testing.assert_frame_equal(
        sample_enrichment_data,
        original_enrichment
    )



# ---------------------------------------------------------
# TEST 19: INVALID ENRICHMENT RESULT
# ---------------------------------------------------------

def test_match_daily_enrichment_invalid_result(
    sample_trend_data
):
    """Test handling of enrichment records with invalid results."""

    enrichment = pd.DataFrame([
        {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "timestamp": "2026-11-01T12:00:00Z",
            "status": "success",
            "result": None
        }
    ])

    result = dashboard.match_daily_enrichment(
        sample_trend_data,
        enrichment
    )

    london = result[result["city"] == "London"].iloc[0]

    assert london["enrichment_status"] == (
        "Enrichment record found, but result is invalid"
    )

    assert pd.isna(london["summary"])


# ---------------------------------------------------------
# TEST 20: DIFFERENT COORDINATES MUST NOT MATCH
# ---------------------------------------------------------

def test_match_daily_enrichment_different_coordinates(
    sample_trend_data
):
    """Test that records from another location are not matched."""

    enrichment = pd.DataFrame([
        {
            "latitude": 51.5000,
            "longitude": -0.1000,
            "timestamp": "2026-11-01T12:00:00Z",
            "status": "success",
            "result": {
                "summary": "Different location"
            }
        }
    ])

    result = dashboard.match_daily_enrichment(
        sample_trend_data,
        enrichment
    )

    london = result[result["city"] == "London"].iloc[0]

    assert london["enrichment_status"] == (
        "No enrichment records available"
    )

    assert pd.isna(london["summary"])
