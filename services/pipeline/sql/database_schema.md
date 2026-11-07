Database Schema Documentation

1. Overview

City Air Tracker uses PostgreSQL (hosted on Supabase) to store location metadata, raw air-pollution observations, transformed analytical data, and pipeline execution logs.

The database schema is maintained in:

services/pipeline/sql/schema.sql

This SQL script uses CREATE TABLE IF NOT EXISTS and CREATE UNIQUE INDEX IF NOT EXISTS so it can be reapplied without recreating existing tables or indexes.

| Table                             | Purpose                                                                 |
| --------------------------------- | ----------------------------------------------------------------------- |
| `public.locations`                | Stores city and geographic metadata.                                    |
| `public.air_pollution_raw`        | Stores parsed raw air-pollution observations.                           |
| `public.air_pollution_gold`       | Stores transformed observations for analytics and dashboard use.        |
| `public.pipeline_runs`            | Tracks pipeline executions, processing counts, and errors.              |
| `public.air_pollution_enrichment` | Stores LLM-generated air-quality interpretations and enrichment status. |

---

2. Locations Table

Table: public.locations

Purpose

Stores location metadata used by the pipeline to identify cities and their geographic coordinates.

Columns

| Column    | PostgreSQL type  | Required? | Description                     |
| --------- | ---------------- | --------- | ------------------------------- |
| city      | TEXT             | Yes       | City name.                      |
| state     | TEXT             | No        | State or administrative region. |
| latitude  | DOUBLE PRECISION | Yes       | Geographic latitude.            |
| longitude | DOUBLE PRECISION | Yes       | Geographic longitude.           |
| timezone  | TEXT             | Yes       | Location's timezone.            |
| country   | TEXT             | Yes       | Country name.                   |

Keys and constraints
Primary key: (city, latitude, longitude)
Foreign keys: None.
Additional unique constraints: None defined in the current schema.

The composite primary key allows the same city name to be associated with different coordinates or geographic locations.

---

3. Raw Air Pollution Table

Table: public.air_pollution_raw

Purpose

Stores parsed air-pollution observations obtained from the OpenWeather Air Pollution API. The table contains observation timestamps, coordinates, AQI values, and pollutant measurements.

The current implementation stores individual observations extracted from the API response, rather than the complete original JSON response.

Columns

| Column    | PostgreSQL type  | Required? | Description                                  |
| --------- | ---------------- | --------- | -------------------------------------------- |
| dt        | BIGINT           | Yes       | Observation timestamp as Unix epoch seconds. |
| latitude  | DOUBLE PRECISION | Yes       | Observation latitude.                        |
| longitude | DOUBLE PRECISION | Yes       | Observation longitude.                       |
| aqi       | SMALLINT         | No        | Air Quality Index value returned by the API. |
| co        | NUMERIC          | No        | Carbon monoxide measurement.                 |
| no        | NUMERIC          | No        | Nitrogen monoxide measurement.               |
| no2       | NUMERIC          | No        | Nitrogen dioxide measurement.                |
| o3        | NUMERIC          | No        | Ozone measurement.                           |
| so2       | NUMERIC          | No        | Sulfur dioxide measurement.                  |
| pm2_5     | NUMERIC          | No        | Fine particulate matter measurement.         |
| pm10      | NUMERIC          | No        | Coarse particulate matter measurement.       |
| nh3       | NUMERIC          | No        | Ammonia measurement.                         |

Keys and constraints
Primary key: (dt, latitude, longitude)
Foreign keys: None.
Additional unique constraints: None defined in the current schema.

The composite primary key identifies an observation by its timestamp and coordinates. Different locations can have observations with the same timestamp without conflicting.

Idempotent loading

The raw loader uses PostgreSQL INSERT ... ON CONFLICT (dt, latitude, longitude) DO UPDATE.

When an observation with the same key already exists, its AQI and pollutant measurements are updated instead of inserting a duplicate row. This allows repeated pipeline runs to process the same observations safely.

---

4. Gold Air Pollution Table

Table: public.air_pollution_gold

Purpose

Stores cleaned and transformed air-pollution observations for analytical queries, reporting, and dashboard visualizations.

The table includes pollutant measurements, AQI information, time-based attributes, and calculated statistics.

Columns

| Column          | PostgreSQL type  | Required? | Description                                       |
| --------------- | ---------------- | --------- | ------------------------------------------------- |
| city            | TEXT             | Yes       | City associated with the observation.             |
| latitude        | DOUBLE PRECISION | Yes       | Geographic latitude.                              |
| longitude       | DOUBLE PRECISION | Yes       | Geographic longitude.                             |
| timestamp       | TIMESTAMPTZ      | Yes       | Observation timestamp.                            |
| transformed_at  | TIMESTAMPTZ      | Yes       | Timestamp when the record was transformed.        |
| aqi             | INTEGER          | No        | Air Quality Index value.                          |
| co              | DOUBLE PRECISION | No        | Carbon monoxide measurement.                      |
| no              | DOUBLE PRECISION | No        | Nitrogen monoxide measurement.                    |
| no2             | DOUBLE PRECISION | No        | Nitrogen dioxide measurement.                     |
| o3              | DOUBLE PRECISION | No        | Ozone measurement.                                |
| so2             | DOUBLE PRECISION | No        | Sulfur dioxide measurement.                       |
| pm2_5           | DOUBLE PRECISION | No        | Fine particulate matter measurement.              |
| pm10            | DOUBLE PRECISION | No        | Coarse particulate matter measurement.            |
| nh3             | DOUBLE PRECISION | No        | Ammonia measurement.                              |
| category        | TEXT             | No        | AQI category assigned during transformation.      |
| time_of_day     | TEXT             | No        | Time-of-day classification.                       |
| day_of_week     | TEXT             | No        | Day-of-week classification.                       |
| month           | TEXT             | No        | Month classification.                             |
| year            | INTEGER          | No        | Observation year.                                 |
| aqi_rolling_avg | DOUBLE PRECISION | No        | Calculated rolling average of AQI.                |
| daily_max       | INTEGER          | No        | Daily maximum AQI.                                |
| daily_min       | INTEGER          | No        | Daily minimum AQI.                                |
| daily_range     | INTEGER          | No        | Difference between daily maximum and minimum AQI. |
| pollution_score | NUMERIC          | No        | Normalized air pollution indicator.               |

Keys and constraints
Primary key: None explicitly defined.
Unique index: (latitude, longitude, timestamp)
Foreign keys: None.

The unique index prevents multiple gold records from having the same coordinates and observation timestamp.

The index supports uniqueness and helps queries that filter or join on these three columns. It is not a declared primary key.

Transformation fields

The table supports additional analytical features, including rolling AQI averages, daily statistics, and time-based classifications.

These fields are nullable in the current schema, allowing records to be stored when some calculated values are unavailable.

---

5. Pipeline Runs Table

Table: public.pipeline_runs

Purpose

Tracks individual pipeline executions and their outcomes. It provides operational visibility into extracted, loaded, and transformed record counts, along with error information.

Columns

| Column              | PostgreSQL type | Required? | Default            | Description                                           |
| ------------------- | --------------- | --------- | ------------------ | ----------------------------------------------------- |
| run_id              | BIGINT          | Yes       | Generated identity | Unique identifier for each pipeline run.              |
| started_at          | TIMESTAMPTZ     | Yes       | NOW()              | Time the run started.                                 |
| finished_at         | TIMESTAMPTZ     | No        | None               | Time the run finished.                                |
| status              | TEXT            | Yes       | 'running'          | Current execution status.                             |
| records_extracted   | INTEGER         | Yes       | None               | Number of records extracted.                          |
| records_loaded      | INTEGER         | Yes       | None               | Number of records loaded into the raw table.          |
| records_transformed | INTEGER         | Yes       | None               | Number of records transformed.                        |
| error_message       | TEXT            | No        | None               | Error details if a run fails or encounters a problem. |

Keys and constraints
Primary key: run_id
Foreign keys: None.
Additional unique constraints: None explicitly defined.
Check constraints

Valid statuses

The pipeline_runs_status_check constraint permits only:

running
success
failure
partial_success

Nonnegative record counts

The pipeline_runs_counts_nonnegative constraint requires all three record counts to be zero or greater.

Valid execution times

The pipeline_runs_finish_after_start constraint requires finished_at to be greater than or equal to started_at whenever finished_at is populated.

These constraints help maintain consistent pipeline execution records.

---

6. Table Relationships

The current schema does not define foreign-key relationships between the five tables.

The following relationships are conceptual and are not enforced by PostgreSQL:

air_pollution_raw and air_pollution_gold contain geographic coordinates that can correspond to records in locations.
pipeline_runs tracks pipeline executions, but the current raw and gold tables do not contain a run_id foreign key referencing it.

If the team later needs to trace individual observations back to a specific execution or enforce location references, foreign keys can be considered as part of a future schema migration.

---

7. Air Pollution Enrichment Table

Table: public.air_pollution_enrichment

Purpose

Stores LLM-generated interpretations of air-pollution observations from the air_pollution_gold table.

Each enrichment record contains a summary, pollutant analysis, and practical recommendation. The table also tracks the model, prompt version, processing status, and errors.

Columns

| Column         | PostgreSQL type  | Required? | Description                                                   |
| -------------- | ---------------- | --------- | ------------------------------------------------------------- |
| id             | BIGINT           | Yes       | Unique enrichment record ID, generated automatically.         |
| latitude       | DOUBLE PRECISION | Yes       | Latitude of the corresponding Gold observation.               |
| longitude      | DOUBLE PRECISION | Yes       | Longitude of the corresponding Gold observation.              |
| timestamp      | TIMESTAMPTZ      | Yes       | Observation timestamp, matching air_pollution_gold.timestamp. |
| model          | TEXT             | Yes       | Name of the LLM used for enrichment.                          |
| prompt_version | TEXT             | Yes       | Version of the prompt used.                                   |
| result         | JSONB            | No        | Structured LLM response.                                      |
| status         | TEXT             | Yes       | Enrichment status: pending, success, or failed.               |
| error_message  | TEXT             | No        | Error details when enrichment fails.                          |
| attempt_count  | INTEGER          | Yes       | Number of enrichment attempts.                                |
| created_at     | TIMESTAMPTZ      | Yes       | Time the enrichment record was created.                       |
| updated_at     | TIMESTAMPTZ      | Yes       | Time the enrichment record was last updated.                  |

Keys and constraints

Primary key: id

Unique constraint:
(latitude, longitude, timestamp, prompt_version)

Foreign keys: None explicitly defined.

Check constraints

Valid statuses:

- pending
- success
- failed

The attempt_count must be zero or greater.

Incremental enrichment

The enrichment process identifies Gold observations that do not have a successful enrichment record for the current prompt version.

Successfully enriched observations are skipped on subsequent runs.

Failed or interrupted enrichment attempts can be retried.

The model name is stored as metadata. Changing the model alone does not create a new enrichment record. A new prompt version allows an observation to be enriched again.

The result is stored as JSONB to support structured enrichment output.

---
