from unittest.mock import Mock
from pathlib import Path
import pytest
import requests
import json

FIXTURES = Path(__file__).parent / "fixtures"

# Fixtures for test_fetch.py
@pytest.fixture
def scripted_get():
    """Build a fake http_get that yields the given outcomes in order."""
    def _build(*outcomes):
        return Mock(side_effect=list(outcomes))  # exceptions in the list are raised
    return _build


@pytest.fixture
def sleeps(monkeypatch):
    """Record sleep calls instead of actually sleeping."""
    calls = []
    monkeypatch.setattr("src.pipeline.extract.fetch.time.sleep", calls.append)
    return calls

@pytest.fixture
def good_payload():
    return json.loads((FIXTURES / "air_pollution_current.json").read_text())