from datetime import datetime, timezone
from extract.config import get_api_key, build_time_window
from extract.locations import load_locations
from extract.fetch import fetch_air_pollution, validate_payload

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

def extract():
    api_key = get_api_key()
    locations = load_locations()
