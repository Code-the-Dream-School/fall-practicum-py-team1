
import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = (
    PROJECT_ROOT
    / "services/pipeline/src/pipeline/transform/raw_to_gold.py"
)


@pytest.fixture(scope="module")
def raw_to_gold_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "raw_to_gold_under_test", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def location():
    return {
        "city": "Fremont",
        "state": "California",
        "country": "US",
        "latitude": 37.5485,
        "longitude": -121.9886,
        "timezone": "America/Los_Angeles",
    }


def make_record(dt, aqi, location):
    return {
        "dt": dt,
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "aqi": aqi,
        "co": 250.0,
        "no": 1.0,
        "no2": 10.0,
        "o3": 30.0,
        "so2": 2.0,
        "pm2_5": 5.0,
        "pm10": 8.0,
        "nh3": 1.0,
    }


def test_transform_empty_raw_records(raw_to_gold_module, location):
    assert raw_to_gold_module.transform([], [location]) == []


def test_transform_rejects_empty_locations(raw_to_gold_module):
    with pytest.raises(ValueError, match="locations table is empty"):
        raw_to_gold_module.transform(
            [make_record(1798761600, 2, {
                "latitude": 37.5485,
                "longitude": -121.9886,
            })],
            [],
        )


@pytest.mark.parametrize(
    ("aqi", "expected_category"),
    [
        (1, "Good"),
        (2, "Fair"),
        (3, "Moderate"),
        (4, "Poor"),
        (5, "Very Poor"),
    ],
)
def test_aqi_category(
    raw_to_gold_module, location, aqi, expected_category
):
    record = make_record(1798761600, aqi, location)

    result = raw_to_gold_module.transform([record], [location])

    assert len(result) == 1
    assert result[0]["category"] == expected_category
    assert result[0]["aqi"] == aqi


def test_daily_statistics_and_rolling_average(
    raw_to_gold_module, location
):
    timestamps = [
        1798761600,
        1798765200,
        1798768800,
    ]
    records = [
        make_record(timestamps[0], 1, location),
        make_record(timestamps[1], 3, location),
        make_record(timestamps[2], 5, location),
    ]

    result = raw_to_gold_module.transform(records, [location])

    assert len(result) == 3
    assert [row["aqi_rolling_avg"] for row in result] == [
        1.0, 2.0, 3.0
    ]
    assert all(row["daily_max"] == 5 for row in result)
    assert all(row["daily_min"] == 1 for row in result)
    assert all(row["daily_range"] == 4 for row in result)


def test_invalid_aqi_records_are_dropped(
    raw_to_gold_module, location
):
    records = [
        make_record(1798761600, 3, location),
        make_record(1798765200, 0, location),
        make_record(1798768800, 6, location),
    ]

    result = raw_to_gold_module.transform(records, [location])

    assert len(result) == 1
    assert result[0]["aqi"] == 3


def test_duplicate_observations_keep_last_record(
    raw_to_gold_module, location
):
    timestamp = 1798761600
    first = make_record(timestamp, 2, location)
    second = make_record(timestamp, 4, location)

    result = raw_to_gold_module.transform(
        [first, second], [location]
    )

    assert len(result) == 1
    assert result[0]["aqi"] == 4


def test_unmatched_coordinates_raise_error(
    raw_to_gold_module, location
):
    record = make_record(1798761600, 2, location)
    record["latitude"] = 37.0

    with pytest.raises(ValueError, match="no matching location"):
        raw_to_gold_module.transform([record], [location])


def test_gold_record_has_transformed_at(
    raw_to_gold_module, location
):
    record = make_record(1798761600, 2, location)

    result = raw_to_gold_module.transform([record], [location])

    assert result[0]["transformed_at"]
    assert result[0]["timestamp"].endswith("+00:00")
