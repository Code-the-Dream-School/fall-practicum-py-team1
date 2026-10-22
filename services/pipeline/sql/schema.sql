CREATE TABLE IF NOT EXISTS public.air_pollution_raw (
    dt BIGINT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    aqi SMALLINT NOT NULL,
    co NUMERIC,
    no NUMERIC,
    no2 NUMERIC,
    o3 NUMERIC,
    so2 NUMERIC,
    pm2_5 NUMERIC,
    pm10 NUMERIC,
    nh3 NUMERIC,
    PRIMARY KEY (dt, latitude, longitude)
);