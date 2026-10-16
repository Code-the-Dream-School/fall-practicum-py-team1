import json
import pytest

from locations import (
    LocationError,
    load_locations,
    validate_location,
)


@pytest.fixture
def location():
    return {
        "city": "Fremont",
        "state": "California",
        "country": "US",
        "lat": 37.5485,
        "lon": -121.9886,
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


def test_load_valid_file(tmp_path):
    config = {
        "locations": [
            {
                "city": "Fremont",
                "country": "US",
                "lat": 37.5,
                "lon": -121.9,
            }
        ]
    }

    path = tmp_path / "locations.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    locations = load_locations(path)

    assert len(locations) == 1
    assert locations[0]["city"] == "Fremont"


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
            }
        ]
    }

    path = tmp_path / "locations.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(LocationError):
        load_locations(path)
