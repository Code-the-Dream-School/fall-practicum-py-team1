from datetime import datetime, timezone
from pipeline.extract.config import get_api_key, build_time_window
from typing import Literal
from pipeline.extract.locations import load_locations
from pipeline.extract.fetch import fetch_air_pollution, validate_payload

class RawRecord:
    def __init__(
            self,
            city: str,
            lat: float,
            lon: float,
            dt: datetime,
            aqi: int,
            co: float | None,
            no: float | None,
            no2: float | None,
            o3: float | None,
            so2: float | None,
            pm2_5: float | None,
            pm10: float | None,
            nh3: float | None,
            ingested_at: datetime
    ):
        self.city = city
        self.lat = lat
        self.lon = lon
        self.dt = dt
        self.aqi = aqi
        self.co = co
        self.no = no
        self.no2 = no2
        self.o3 = o3
        self.so2 = so2
        self.pm2_5 = pm2_5
        self.pm10 = pm10
        self.nh3 = nh3
        self.ingested_at = ingested_at

def load_raw(city: str, payload: dict, warnings: list) -> RawRecord:
    coord = payload.get('coord', {})
    ls = payload.get('list', {})
    main = ls.get('main', {})
    comp = ls.get('components', {})
    dt = ls.get('dt')
    ingested_at = datetime.now(tz=timezone.utc)
    return RawRecord(
        city=city,
        lat=coord.get('lat'),
        lon=coord.get('lon'),
        dt=dt,
        aqi=main.get('aqi'),
        co=comp.get('co'),
        no=comp.get('no'),
        no2=comp.get('no2'),
        o3=comp.get('o3'),
        so2=comp.get('so2'),
        pm2_5=comp.get('pm2_5'),
        pm10=comp.get('pm10'),
        nh3=comp.get('nh3'),
        ingested_at=ingested_at,
        warnings=warnings
    )

def extract(kind: Literal['current', 'history'], start_ts: datetime | None = None, end_ts: datetime | None = None, **kwarg) -> list[RawRecord]:
    raw_records = []
    api_key = get_api_key()
    locations = load_locations()
    if start_ts and end_ts:
        start_ts, end_ts = build_time_window(start_ts, end_ts)
    for loc in locations:
        city = loc.get('city')
        lat = loc.get('lat')
        lon = lon.get('lon')
        results, warnings = fetch_air_pollution(
            kind=kind,
            lat=lat,
            lon=lon,
            api_key=api_key,
            start_ts=start_ts,
            end_ts=end_ts,
            **kwarg
        )
        raw_records.append(load_raw(city, results, warnings))
    return raw_records

if __name__ == "__main__":
    print("=" * 25)
    print("Test current call")
    print("=" * 25)
    raw_records = extract('current')
    for rec in raw_records:
        print(rec)