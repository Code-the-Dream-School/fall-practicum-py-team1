
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class LocationError(ValueError):
    """Raised when a location is invalid."""


def validate_timezone(timezone):
    """Validate a timezone identifier and return it unchanged."""

    if not isinstance(timezone, str) or not timezone.strip():
        raise LocationError("Timezone is required")

    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise LocationError(f"Invalid timezone: {timezone}") from exc

    return timezone


def validate_location(raw):
    """Validate one location dictionary and return it unchanged."""

    if not isinstance(raw, dict):
        raise LocationError("Location must be a dictionary")

    city = raw.get("city")
    country = raw.get("country")
    lat = raw.get("lat")
    lon = raw.get("lon")
    timezone = raw.get("timezone")

    if not isinstance(city, str) or not city.strip():
        raise LocationError("City is required")

    if not isinstance(country, str) or not country.strip():
        raise LocationError("Country is required")

    # bool is a subclass of int, so reject it explicitly.
    if isinstance(lat, bool) or not isinstance(lat, (int, float)):
        raise LocationError("Latitude must be numeric")

    if not math.isfinite(lat):
        raise LocationError("Latitude must be finite")

    if isinstance(lon, bool) or not isinstance(lon, (int, float)):
        raise LocationError("Longitude must be numeric")

    if not math.isfinite(lon):
        raise LocationError("Longitude must be finite")

    if not -90 <= lat <= 90:
        raise LocationError("Latitude must be between -90 and 90")

    if not -180 <= lon <= 180:
        raise LocationError("Longitude must be between -180 and 180")

    validate_timezone(timezone)

    return raw


def load_locations(path=None):
    """Load a JSON locations file and validate its entries."""

    if path is None:
        path = Path(__file__).parent / "locations.json"

    try:
        with Path(path).open("r", encoding="utf-8") as file:
            config = json.load(file)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "Locations file is missing, unreadable, or invalid"
        ) from exc

    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object")

    locations = config.get("locations")

    if not isinstance(locations, list) or not locations:
        raise ValueError("Locations list must not be empty")

    for location in locations:
        validate_location(location)

    return locations
