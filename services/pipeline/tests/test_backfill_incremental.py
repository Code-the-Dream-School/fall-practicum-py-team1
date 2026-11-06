
from datetime import date

import pytest

from pipeline.orchestration.backfill_incremental import (
    build_enrichment_key,
    iter_batches,
    select_records_for_enrichment,
    validate_mode_dates,
)


@pytest.fixture
def valid_record():
    return {
        "city": "Fremont",
        "latitude": 37.5485,
        "longitude": -121.9886,
        "timestamp": "2026-10-21T02:19:03+00:00",
        "aqi": 2,
        "co": 145.19,
        "no": 0,
        "no2": 1.65,
        "o3": 81.8,
        "so2": 1.0,
        "pm2_5": 2.38,
        "pm10": 5.45,
        "nh3": 0.01,
    }


def test_backfill_requires_both_dates():
    with pytest.raises(ValueError):
        validate_mode_dates(
            "backfill",
            start_date="2024-01-01",
        )


def test_backfill_rejects_end_before_start():
    with pytest.raises(ValueError):
        validate_mode_dates(
            "backfill",
            start_date="2024-06-01",
            end_date="2024-01-01",
        )


def test_backfill_accepts_valid_dates():
    result = validate_mode_dates(
        "backfill",
        start_date="2024-01-01",
        end_date="2024-06-30",
    )

    assert result == (
        date(2024, 1, 1),
        date(2024, 6, 30),
    )


def test_incremental_rejects_dates():
    with pytest.raises(ValueError):
        validate_mode_dates(
            "incremental",
            start_date="2024-01-01",
            end_date="2024-06-30",
        )


def test_new_eligible_record_is_selected(valid_record):
    selected = select_records_for_enrichment(
        gold_records=[valid_record],
        successful_keys=set(),
        prompt_version="v1",
    )

    assert selected == [valid_record]


def test_successful_record_is_skipped(valid_record):
    successful_key = build_enrichment_key(
        valid_record, "v1"
    )

    selected = select_records_for_enrichment(
        gold_records=[valid_record],
        successful_keys={successful_key},
        prompt_version="v1",
    )

    assert selected == []


def test_new_prompt_version_allows_reenrichment(valid_record):
    successful_key = build_enrichment_key(
        valid_record, "v1"
    )

    selected = select_records_for_enrichment(
        gold_records=[valid_record],
        successful_keys={successful_key},
        prompt_version="v2",
    )

    assert selected == [valid_record]


def test_model_is_not_part_of_enrichment_identity(valid_record):
    key_before = build_enrichment_key(
        valid_record, "v1"
    )

    # Model metadata does not affect the identity.
    record_with_model = {
        **valid_record,
        "model": "gpt-4o-mini",
    }

    key_after = build_enrichment_key(
        record_with_model, "v1"
    )

    assert key_before == key_after
    assert len(key_after) == 4


def test_ineligible_aqi_is_skipped(valid_record):
    invalid_record = {
        **valid_record,
        "aqi": 6,
    }

    selected = select_records_for_enrichment(
        gold_records=[invalid_record],
        successful_keys=set(),
    )

    assert selected == []


def test_record_needs_at_least_one_pollutant(valid_record):
    invalid_record = {
        **valid_record,
        "co": None,
        "no": None,
        "no2": None,
        "o3": None,
        "so2": None,
        "pm2_5": None,
        "pm10": None,
        "nh3": None,
    }

    selected = select_records_for_enrichment(
        gold_records=[invalid_record],
        successful_keys=set(),
    )

    assert selected == []


def test_batches_split_records():
    records = [{"id": number} for number in range(5)]

    batches = list(
        iter_batches(records, batch_size=2)
    )

    assert [len(batch) for batch in batches] == [2, 2, 1]


def test_batch_size_must_be_positive():
    with pytest.raises(ValueError):
        list(
            iter_batches([{"id": 1}], batch_size=0)
        )
