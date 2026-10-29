Database Schema Documentation
1. Overview

City Air Tracker uses PostgreSQL (hosted on Supabase) to store location metadata, raw air-pollution observations, transformed analytical data, and pipeline execution logs.

The database schema is maintained in:

services/pipeline/sql/schema.sql

This SQL script uses CREATE TABLE IF NOT EXISTS and CREATE UNIQUE INDEX IF NOT EXISTS so it can be reapplied without recreating existing tables or indexes.

Tables
Table	                            Purpose
public.locations	        Stores city and geographic metadata.
public.air_pollution_raw	Stores parsed raw air-pollution observations.
public.air_pollution_gold	Stores transformed observations for analytics and dashboard use.
public.pipeline_runs	    Tracks pipeline executions, processing counts, and errors.

--------------------------------------------------------------------------------------------------------------------------------------

2. Locations Table

Table: public.locations

Purpose

Stores location metadata used by the pipeline to identify cities and their geographic coordinates.

Columns
Column       PostgreSQL_type   	         Required?	            Description
city	          TEXT	                    Yes      	        City name.
state	          TEXT	                    No      	State or administrative region.
latitude	    DOUBLE PRECISION        	Yes         	Geographic latitude.
longitude	    DOUBLE PRECISION	        Yes	            Geographic longitude.
timezone	      TEXT	                    Yes	            Location's timezone.
country	          TEXT	                    Yes	                    Country name.


Keys and constraints
Primary key: (city, latitude, longitude)
Foreign keys: None.
Additional unique constraints: None defined in the current schema.

The composite primary key allows the same city name to be associated with different coordinates or geographic locations.



--------------------------------------------------------------------------------------------------------------------------------------




3. Raw Air Pollution Table

Table: public.air_pollution_raw

Purpose

Stores parsed air-pollution observations obtained from the OpenWeather Air Pollution API. The table contains observation timestamps, coordinates, AQI values, and pollutant measurements.

The current implementation stores individual observations extracted from the API response, rather than the complete original JSON response.

Columns
Column	        PostgreSQL_type	                Required?	                            Description
dt	                BIGINT	                        Yes	                Observation timestamp as Unix epoch seconds.
latitude    	DOUBLE PRECISION	                Yes	                            Observation latitude.
longitude	    DOUBLE PRECISION	                Yes	                            Observation longitude.
aqi	                SMALLINT	                    No	                Air Quality Index value returned by the API.
co	                NUMERIC	                        No	                        Carbon monoxide measurement.
no	                NUMERIC                        	No	                        Nitrogen monoxide measurement.
no2             	NUMERIC	                        No	                        Nitrogen dioxide measurement.
o3	                NUMERIC	                        No	                        Ozone measurement.
so2	                NUMERIC	                        No	                        Sulfur dioxide measurement.
pm2_5	            NUMERIC	                        No	                        Fine particulate matter measurement.
pm10	            NUMERIC	                        No	                        Coarse particulate matter measurement.
nh3	                NUMERIC	                        No	                        Ammonia measurement.

Keys and constraints
Primary key: (dt, latitude, longitude)
Foreign keys: None.
Additional unique constraints: None defined in the current schema.

The composite primary key identifies an observation by its timestamp and coordinates. Different locations can have observations with the same timestamp without conflicting.

Idempotent loading

The raw loader uses PostgreSQL INSERT ... ON CONFLICT (dt, latitude, longitude) DO UPDATE.

When an observation with the same key already exists, its AQI and pollutant measurements are updated instead of inserting a duplicate row. This allows repeated pipeline runs to process the same observations safely.





--------------------------------------------------------------------------------------------------------------------------------------



4. Gold Air Pollution Table

Table: public.air_pollution_gold

Purpose

Stores cleaned and transformed air-pollution observations for analytical queries, reporting, and dashboard visualizations.

The table includes pollutant measurements, AQI information, time-based attributes, and calculated statistics.

Columns
Column	        PostgreSQL_type	                        Required?	                        Description
city	            TEXT	                                Yes	                    City associated with the observation.
latitude	    DOUBLE PRECISION	                        Yes	                        Geographic latitude.
longitude	    DOUBLE PRECISION	                        Yes	                        Geographic longitude.
timestamp	      TIMESTAMPTZ	                            Yes	                        Observation timestamp.
transformed_at	  TIMESTAMPTZ	                            Yes	                Timestamp when the record was transformed.
aqi	                INTEGER	                                 No	                        Air Quality Index value.
co	            DOUBLE PRECISION	                         No	                        Carbon monoxide measurement.
no	            DOUBLE PRECISION	                         No                     	Nitrogen monoxide measurement.
no2         	DOUBLE PRECISION	                         No                     	Nitrogen dioxide measurement.
o3	            DOUBLE PRECISION	                         No	                            Ozone measurement.
so2         	DOUBLE PRECISION                          	 No                         Sulfur dioxide measurement.
pm2_5	        DOUBLE PRECISION	                         No                     	Fine particulate matter measurement.
pm10	        DOUBLE PRECISION	                         No	                        Coarse particulate matter measurement.
nh3	            DOUBLE PRECISION	                         No	                        Ammonia measurement.
category	        TEXT	                                 No	                AQI category assigned during transformation.
time_of_day     	TEXT	                                 No	                         Time-of-day classification.
day_of_week     	TEXT	                                 No	                       Day-of-week classification.
month           	TEXT                                     No	                            Month classification.
year            	INTEGER	                                 No	                                Observation year.
aqi_rolling_avg	DOUBLE PRECISION                             No	                    Calculated rolling average of AQI.
daily_max	        INTEGER                                  No                             	Daily maximum AQI.
daily_min       	INTEGER                                  No	                                Daily minimum AQI.
daily_range	        INTEGER                                  No             	Difference between daily maximum and minimum AQI.



Keys and constraints
Primary key: None explicitly defined.
Unique index: (latitude, longitude, timestamp)
Foreign keys: None.

The unique index prevents multiple gold records from having the same coordinates and observation timestamp.

The index supports uniqueness and helps queries that filter or join on these three columns. It is not a declared primary key.

Transformation fields

The table supports additional analytical features, including rolling AQI averages, daily statistics, and time-based classifications.

These fields are nullable in the current schema, allowing records to be stored when some calculated values are unavailable.



--------------------------------------------------------------------------------------------------------------------------------------



5. Pipeline Runs Table

Table: public.pipeline_runs

Purpose

Tracks individual pipeline executions and their outcomes. It provides operational visibility into extracted, loaded, and transformed record counts, along with error information.

Columns
Column              	PostgreSQL_type	                Required?                       	Default	Description
run_id                  	BIGINT                        Yes	        Generated identity	Unique identifier for each pipeline run.
started_at	            TIMESTAMPTZ	                      Yes	                        NOW()	Time the run started.
finished_at         	TIMESTAMPTZ	                      No	                        None	Time the run finished.
status	                    TEXT	                      Yes                   	'running'	Current execution status.
records_extracted	      INTEGER	                      Yes	                       	Number of records extracted.
records_loaded	          INTEGER	                      Yes	            	Number of records loaded into the raw table.
records_transformed	       INTEGER                        Yes	                    Number of records transformed.
error_message	            TEXT                           No	       	Error details if a run fails or encounters a problem.


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



--------------------------------------------------------------------------------------------------------------------------------------



6. Table Relationships

The current schema does not define foreign-key relationships between the four tables.

The following relationships are conceptual and are not enforced by PostgreSQL:

air_pollution_raw and air_pollution_gold contain geographic coordinates that can correspond to records in locations.
pipeline_runs tracks pipeline executions, but the current raw and gold tables do not contain a run_id foreign key referencing it.

If the team later needs to trace individual observations back to a specific execution or enforce location references, foreign keys can be considered as part of a future schema migration.