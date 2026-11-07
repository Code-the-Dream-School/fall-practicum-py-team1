from unittest.mock import MagicMock

import pytest

from pipeline.enrichment.service import run_enrichment


@pytest.fixture
def gold_record():
    return {
        "city": "Carmichael",
        "latitude": 38.6171,
        "longitude": -121.3283,
        "timestamp": "2026-10-01T12:00:00+00:00",
        "aqi": 2,
        "category": "Fair",
        "pollution_score": 0.25,
        "co": 250.0,
        "no": 0.5,
        "no2": 12.0,
        "o3": 40.0,
        "so2": 1.0,
        "pm2_5": 8.0,
        "pm10": 15.0,
        "nh3": 2.0,
    }


@pytest.fixture
def mock_enricher():
    enricher = MagicMock()
    enricher.enrich.return_value = {
        "summary": "Air quality is fair.",
        "pollutant_analysis": "Pollutant levels are relatively low.",
        "recommendation": "Normal outdoor activities are reasonable.",
    }
    return enricher

class FakeSupabase:
    """In-memory Supabase mock for enrichment tests."""

    def __init__(self, gold_records=None):
        self.tables = {
            "air_pollution_gold": gold_records or [],
            "air_pollution_enrichment": [],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


class FakeQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.start = 0
        self.end = None
        self.payload = None

    def select(self, columns):
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def upsert(self, payload, on_conflict=None):
        self.payload = payload
        return self

    def execute(self):
        if self.payload is not None:
            rows = self.database.tables[self.table_name]
            key_fields = (
                "latitude",
                "longitude",
                "timestamp",
                "prompt_version",
            )

            payload_key = tuple(
                self.payload[field] for field in key_fields
            )

            for index, row in enumerate(rows):
                row_key = tuple(row[field] for field in key_fields)
                if row_key == payload_key:
                    rows[index] = self.payload
                    break
            else:
                rows.append(self.payload)

            return MagicMock(data=[self.payload])

        rows = self.database.tables[self.table_name]
        return MagicMock(
            data=rows[self.start:self.end + 1]
        )


def test_successful_record_is_skipped_on_rerun(
    gold_record,
    mock_enricher,
):
    database = FakeSupabase([gold_record])

    first_result = run_enrichment(
        supabase_client=database,
        enricher=mock_enricher,
    )

    assert first_result == {
        "total": 1,
        "skipped": 0,
        "succeeded": 1,
        "failed": 0,
    }

    assert len(database.tables["air_pollution_enrichment"]) == 1
    assert database.tables["air_pollution_enrichment"][0]["status"] == "success"

    second_result = run_enrichment(
        supabase_client=database,
        enricher=mock_enricher,
    )

    assert second_result == {
        "total": 1,
        "skipped": 1,
        "succeeded": 0,
        "failed": 0,
    }

    assert mock_enricher.enrich.call_count == 1
    assert len(database.tables["air_pollution_enrichment"]) == 1

def test_failed_record_can_be_retried(
    gold_record,
    mock_enricher,
):
    database = FakeSupabase([gold_record])

    mock_enricher.enrich.side_effect = [
        ValueError("Temporary LLM error"),
        {
            "summary": "Air quality is fair.",
            "pollutant_analysis": "Pollutant levels are relatively low.",
            "recommendation": "Normal outdoor activities are reasonable.",
        },
    ]

    first_result = run_enrichment(
        supabase_client=database,
        enricher=mock_enricher,
    )

    saved_record = database.tables["air_pollution_enrichment"][0]

    assert first_result["failed"] == 1
    assert saved_record["status"] == "failed"
    assert saved_record["error_message"] == "Temporary LLM error"
    assert saved_record["attempt_count"] == 1

    second_result = run_enrichment(
        supabase_client=database,
        enricher=mock_enricher,
    )

    saved_record = database.tables["air_pollution_enrichment"][0]

    assert second_result["succeeded"] == 1
    assert saved_record["status"] == "success"
    assert saved_record["attempt_count"] == 2
    assert saved_record["error_message"] is None
    assert mock_enricher.enrich.call_count == 2
    assert len(database.tables["air_pollution_enrichment"]) == 1

def test_one_failure_does_not_stop_batch(
    gold_record,
    mock_enricher,
):
    second_record = {
        **gold_record,
        "latitude": 38.6,
        "longitude": -121.3,
        "timestamp": "2026-10-01T13:00:00+00:00",
    }

    database = FakeSupabase([gold_record, second_record])

    mock_enricher.enrich.side_effect = [
        ValueError("Temporary LLM error"),
        {
            "summary": "Air quality is fair.",
            "pollutant_analysis": "Pollutant levels are relatively low.",
            "recommendation": "Normal outdoor activities are reasonable.",
        },
    ]

    result = run_enrichment(
        supabase_client=database,
        enricher=mock_enricher,
    )

    saved_records = database.tables["air_pollution_enrichment"]

    assert result["total"] == 2
    assert result["failed"] == 1
    assert result["succeeded"] == 1
    assert len(saved_records) == 2
    assert saved_records[0]["status"] == "failed"
    assert saved_records[1]["status"] == "success"
    assert mock_enricher.enrich.call_count == 2

def test_new_prompt_version_creates_new_enrichment(
    gold_record,
    mock_enricher,
):
    database = FakeSupabase([gold_record])

    run_enrichment(
        supabase_client=database,
        enricher=mock_enricher,
        prompt_version="v1",
    )

    result = run_enrichment(
        supabase_client=database,
        enricher=mock_enricher,
        prompt_version="v2",
    )

    saved_records = database.tables["air_pollution_enrichment"]

    assert result["succeeded"] == 1
    assert len(saved_records) == 2
    assert {row["prompt_version"] for row in saved_records} == {"v1", "v2"}
    assert mock_enricher.enrich.call_count == 2

def test_duplicate_gold_observation_is_processed_once(
    gold_record,
    mock_enricher,
):
    database = FakeSupabase([gold_record, gold_record.copy()])

    result = run_enrichment(
        supabase_client=database,
        enricher=mock_enricher,
    )

    assert result == {
        "total": 2,
        "skipped": 1,
        "succeeded": 1,
        "failed": 0,
    }

    assert mock_enricher.enrich.call_count == 1
    assert len(database.tables["air_pollution_enrichment"]) == 1