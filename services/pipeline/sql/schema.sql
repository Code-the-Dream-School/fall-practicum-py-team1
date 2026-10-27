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
CREATE TABLE IF NOT EXISTS public.locations (
    city TEXT NOT NULL,
    state TEXT,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    timezone TEXT NOT NULL,
    country TEXT NOT NULL,
    CONSTRAINT locations_pkey PRIMARY KEY (city, latitude, longitude)
);

CREATE TABLE IF NOT EXISTS public.air_pollution_gold (
    city TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    transformed_at TIMESTAMPTZ NOT NULL,
    aqi INTEGER NOT NULL,
    co DOUBLE PRECISION,
    no DOUBLE PRECISION,
    no2 DOUBLE PRECISION,
    o3 DOUBLE PRECISION,
    so2 DOUBLE PRECISION,
    pm2_5 DOUBLE PRECISION,
    pm10 DOUBLE PRECISION,
    nh3 DOUBLE PRECISION,
    category TEXT,
    time_of_day TEXT,
    day_of_week TEXT,
    month TEXT,
    year INTEGER,
    aqi_rolling_avg DOUBLE PRECISION,
    daily_max INTEGER,
    daily_min INTEGER,
    daily_range INTEGER
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_air_pollution_gold_location_timestamp
    ON public.air_pollution_gold (latitude, longitude, "timestamp");


-- Pipeline run tracking and operational logs
CREATE TABLE IF NOT EXISTS public.pipeline_runs (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    records_extracted INTEGER NOT NULL DEFAULT 0,
    records_loaded INTEGER NOT NULL DEFAULT 0,
    records_transformed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,

    CONSTRAINT pipeline_runs_status_check
        CHECK (
            status IN ('running', 'success', 'failure', 'partial_success')
        ),

    CONSTRAINT pipeline_runs_counts_nonnegative
        CHECK (
            records_extracted >= 0
            AND records_loaded >= 0
            AND records_transformed >= 0
        ),

    CONSTRAINT pipeline_runs_finish_after_start
        CHECK (
            finished_at IS NULL OR finished_at >= started_at
        )
);
