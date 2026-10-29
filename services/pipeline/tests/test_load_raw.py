from unittest.mock import Mock
from pipeline.extract.extract import RawRecord
from pipeline.load.postgreSQL_schema_raw import map_records, load_records


def test_map_records_converts_raw_record_to_database_row():
    item = RawRecord(
        city="Fremont",
        lat=37.5485,
        lon=-121.9886,
        dt=1792542180,
        aqi=2,
        co=142.98,
        no=0.03,
        no2=1.13,
        o3=82.32,
        so2=0.85,
        pm2_5=2.36,
        pm10=6.45,
        nh3=0,
    )

    rows = map_records([item])

    assert len(rows) == 1
    assert rows[0]["dt"] == 1792542180
    assert rows[0]["latitude"] == 37.5485
    assert rows[0]["longitude"] == -121.9886
    assert rows[0]["aqi"] == 2
    assert rows[0]["pm2_5"] == 2.36
    assert "city" not in rows[0]


def test_map_records_handles_empty_input():
    assert map_records([]) == []



def test_load_records_skips_database_for_empty_input():
    from unittest.mock import Mock
    from pipeline.load.postgreSQL_schema_raw import load_records

    client = Mock()

    result = load_records([], client)

    assert result == 0
    client.table.assert_not_called()




def test_load_records_upserts_with_composite_key():
    from unittest.mock import Mock
    from pipeline.load.postgreSQL_schema_raw import load_records

    item = RawRecord(
        city="Fremont",
        lat=37.5485,
        lon=-121.9886,
        dt=1792542180,
        aqi=2,
        co=142.98,
        no=0.03,
        no2=1.13,
        o3=82.32,
        so2=0.85,
        pm2_5=2.36,
        pm10=6.45,
        nh3=0,
    )

    client = Mock()
    client.table.return_value.upsert.return_value.execute.return_value.data = [
        {"dt": 1792542180}
    ]

    result = load_records([item], client)

    assert result == 1
    client.table.assert_called_once_with("air_pollution_raw")
    client.table.return_value.upsert.assert_called_once_with(
        [{
            "dt": 1792542180,
            "latitude": 37.5485,
            "longitude": -121.9886,
            "aqi": 2,
            "co": 142.98,
            "no": 0.03,
            "no2": 1.13,
            "o3": 82.32,
            "so2": 0.85,
            "pm2_5": 2.36,
            "pm10": 6.45,
            "nh3": 0,
        }],
        on_conflict="dt,latitude,longitude",
    )