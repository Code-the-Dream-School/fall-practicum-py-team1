from datetime import datetime, timezone

import pytest

from pipeline.extract.config import (
    MissingApiKeyError,
    build_time_window,
    get_api_key,
)


def test_get_api_key_returns_key(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")

    assert get_api_key() == "test-key"


def test_get_api_key_raises_when_missing(monkeypatch):
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)

    with pytest.raises(MissingApiKeyError):
        get_api_key()


def test_get_api_key_raises_when_empty(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "   ")

    with pytest.raises(MissingApiKeyError):
        get_api_key()


def test_build_time_window_returns_unix_timestamps():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)

    assert build_time_window(start, end) == (
        1767225600,
        1767312000,
    )


def test_build_time_window_rejects_naive_start():
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="Start datetime"):
        build_time_window(start, end)


def test_build_time_window_rejects_naive_end():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2)

    with pytest.raises(ValueError, match="End datetime"):
        build_time_window(start, end)


def test_build_time_window_rejects_start_after_end():
    start = datetime(2026, 1, 2, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="must not be after"):
        build_time_window(start, end)
