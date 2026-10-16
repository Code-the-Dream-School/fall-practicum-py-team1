import json
import tempfile
import unittest
from pathlib import Path

from locations import (
    LocationError,
    load_locations,
    validate_location,
)


class TestValidateLocation(unittest.TestCase):

    def setUp(self):
        self.location = {
            "city": "Fremont",
            "state": "California",
            "country": "US",
            "lat": 37.5485,
            "lon": -121.9886,
        }

    def test_valid_location(self):
        self.assertEqual(
            validate_location(self.location),
            self.location,
        )
    def test_missing_city(self):
        location = {**self.location, "city": ""}
        with self.assertRaises(LocationError):
            validate_location(location)

    def test_missing_country(self):
        location = {**self.location}
        del location["country"]
        with self.assertRaises(LocationError):
            validate_location(location)

    def test_invalid_latitude(self):
        location = {**self.location, "lat": 95}
        with self.assertRaises(LocationError):
            validate_location(location)

    def test_invalid_longitude(self):
        location = {**self.location, "lon": -200}
        with self.assertRaises(LocationError):
            validate_location(location)

    def test_nonnumeric_coordinates(self):
        location = {**self.location, "lat": "north"}
        with self.assertRaises(LocationError):
            validate_location(location)

class TestLoadLocations(unittest.TestCase):

    def test_load_valid_file(self):
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

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "locations.json"
            path.write_text(json.dumps(config), encoding="utf-8")

            locations = load_locations(path)

            self.assertEqual(len(locations), 1)
            self.assertEqual(locations[0]["city"], "Fremont")

    def test_missing_file(self):
        with self.assertRaises(ValueError):
            load_locations("does_not_exist.json")

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "empty.json"
            path.write_text("", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_locations(path)

    def test_empty_locations_list(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "locations.json"
            path.write_text(
                json.dumps({"locations": []}),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_locations(path)

    def test_invalid_location_in_file(self):
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

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "locations.json"
            path.write_text(json.dumps(config), encoding="utf-8")

            with self.assertRaises(LocationError):
                load_locations(path)


if __name__ == "__main__":
    unittest.main()