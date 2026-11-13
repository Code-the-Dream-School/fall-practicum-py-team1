CREATE TABLE IF NOT EXISTS public.air_pollution_raw (
    dt BIGINT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    aqi DOUBLE PRECISION,
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

create table public.air_pollution_gold (
  city text not null,
  latitude double precision not null,
  longitude double precision not null,
  "timestamp" timestamp with time zone not null,
  transformed_at timestamp with time zone not null,
  aqi integer not null,
  co double precision null,
  no double precision null,
  no2 double precision null,
  o3 double precision null,
  so2 double precision null,
  pm2_5 double precision null,
  pm10 double precision null,
  nh3 double precision null,
  category text null,
  time_of_day text null,
  day_of_week text null,
  month text null,
  year integer null,
  aqi_rolling_avg double precision null,
  daily_max integer null,
  daily_min integer null,
  daily_range integer null,
  pollution_score numeric null
) TABLESPACE pg_default;

create unique INDEX IF not exists uq_air_pollution_gold_location_timestamp on public.air_pollution_gold using btree (latitude, longitude, "timestamp") TABLESPACE pg_default;

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
