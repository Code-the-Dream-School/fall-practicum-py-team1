
import json

import pytest

from pipeline.extract.locations import (
    LocationError,
    load_locations,
    validate_location,
    validate_timezone,
)


@pytest.fixture
def location():
    return {
        "city": "Fremont",
        "state": "California",
        "country": "US",
        "lat": 37.5485,
        "lon": -121.9886,
        "timezone": "America/Los_Angeles",
    }


def test_valid_location(location):
    assert validate_location(location) == location


def test_missing_city(location):
    location["city"] = ""

    with pytest.raises(LocationError):
        validate_location(location)


def test_missing_country(location):
    del location["country"]

    with pytest.raises(LocationError):
        validate_location(location)


def test_invalid_latitude(location):
    location["lat"] = 95

    with pytest.raises(LocationError):
        validate_location(location)


def test_invalid_longitude(location):
    location["lon"] = -200

    with pytest.raises(LocationError):
        validate_location(location)


def test_nonnumeric_coordinates(location):
    location["lat"] = "north"

    with pytest.raises(LocationError):
        validate_location(location)


def test_valid_timezone():
    assert (
        validate_timezone("America/Los_Angeles")
        == "America/Los_Angeles"
    )


def test_missing_timezone(location):
    del location["timezone"]

    with pytest.raises(LocationError, match="Timezone is required"):
        validate_location(location)


@pytest.mark.parametrize("timezone", ["", "   ", None, 123])
def test_invalid_timezone_value(timezone):
    with pytest.raises(LocationError):
        validate_timezone(timezone)


def test_unknown_timezone():
    with pytest.raises(LocationError, match="Invalid timezone"):
        validate_timezone("Invalid/Timezone")


def test_load_valid_file(tmp_path):
    config = {
        "locations": [
            {
                "city": "Fremont",
                "country": "US",
                "lat": 37.5,
                "lon": -121.9,
                "timezone": "America/Los_Angeles",
            }
        ]
    }

    path = tmp_path / "locations.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    locations = load_locations(path)

    assert len(locations) == 1
    assert locations[0]["city"] == "Fremont"
    assert locations[0]["timezone"] == "America/Los_Angeles"


def test_missing_file(tmp_path):
    path = tmp_path / "does_not_exist.json"

    with pytest.raises(ValueError):
        load_locations(path)


def test_empty_file(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError):
        load_locations(path)


def test_empty_locations_list(tmp_path):
    path = tmp_path / "locations.json"
    path.write_text(
        json.dumps({"locations": []}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_locations(path)


def test_invalid_location_in_file(tmp_path):
    config = {
        "locations": [
            {
                "city": "Fremont",
                "country": "US",
                "lat": 95,
                "lon": -121.9,
                "timezone": "America/Los_Angeles",
            }
        ]
    }

    path = tmp_path / "locations.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(LocationError):
        load_locations(path)


def test_invalid_timezone_in_file(tmp_path):
    config = {
        "locations": [
            {
                "city": "Fremont",
                "country": "US",
                "lat": 37.5485,
                "lon": -121.9886,
                "timezone": "Invalid/Timezone",
            }
        ]
    }

    path = tmp_path / "locations.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(LocationError):
        load_locations(path)
