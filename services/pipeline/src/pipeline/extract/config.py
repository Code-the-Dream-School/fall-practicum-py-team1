import os
from datetime import datetime, timezone


class MissingApiKeyError(Exception):
    """Raised when the OpenWeather API key is missing."""


def get_api_key() -> str:
    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key or not api_key.strip():
        raise MissingApiKeyError(
            "OPENWEATHER_API_KEY is missing or empty."
        )

    return api_key.strip()


def build_time_window(
    start: datetime,
    end: datetime,
) -> tuple[int, int]:
    if start.tzinfo is None or start.utcoffset() is None:
        raise ValueError("Start datetime must be timezone-aware.")

    if end.tzinfo is None or end.utcoffset() is None:
        raise ValueError("End datetime must be timezone-aware.")

    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)

    if start_utc > end_utc:
        raise ValueError("Start datetime must not be after end datetime.")

    return int(start_utc.timestamp()), int(end_utc.timestamp())
