Proposed Data Contract — City Air Tracker
-----------------------------------------
Status: Draft for mentor/team review
Version: 0.1
Purpose: Define a proposed common structure for the raw and gold data used by the City Air Tracker pipeline. This document is intended for discussion and may be revised based on mentor and team feedback.

1. Purpose
----------

This data contract defines:
The expected structure of data received from the OpenWeather Air Pollution API
The proposed structure of the raw dataset
The proposed structure of the gold dataset
Data types and required/optional fields
Proposed function interfaces between pipeline stages
Basic data quality expectations
Questions that need to be reviewed and agreed upon by the team
This is a proposed contract and is not intended to represent final team decisions.

2. Proposed Data Flow
---------------------

OpenWeather Air Pollution API
            |
            v
        extract()
            |
            v
       Raw Records
            |
            v
        load_raw()
            |
            v
         Raw Data
            |
            v
        transform()
            |
            v
       Gold Records
            |
            v
        load_gold()
            |
            v
        Gold Data


3. Source API
--------------

The source for air-quality data is the OpenWeather Air Pollution API.
A sample API response currently observed is:
{
    'coord': {
        'lon': 50,
        'lat': 50
    },
    'list': [
        {
            'main': {
                'aqi': 2
            },
            'components': {
                'co': 139.58,
                'no': 0,
                'no2': 0.33,
                'o3': 91.18,
                'so2': 2.13,
                'pm2_5': 17.33,
                'pm10': 39.01,
                'nh3': 0
            },
            'dt': 1791312257
        }
    ]
}

The API response contains:
Geographic coordinates
OpenWeather AQI
Pollutant measurements
A Unix timestamp
The pipeline may add additional metadata such as city and ingestion time.

4. Raw Data Contract
--------------------

4.1 Proposed Raw Schema
------------------------
|-------------|----------|----------|-------------------------------------|--------------------------------------------------|
| Field       | Type     | Required | Source                              | Description                                      |
|-------------|----------|----------|-------------------------------------|--------------------------------------------------|
| city        | string   | Yes*     | Pipeline                            | City associated with the coordinates/request     |
| latitude    | float    | Yes      | OpenWeather coord.lat               | Geographic latitude                              |
| longitude   | float    | Yes      | OpenWeather coord.lon               | Geographic longitude                             |
| timestamp   | datetime | Yes      | OpenWeather list[].dt               | Observation time after converting Unix timestamp |
| aqi         | integer  | Yes      | OpenWeather list[].main.aqi         | OpenWeather Air Quality Index                    |
| co          | float    | Yes      | OpenWeather list[].components.co    | Carbon monoxide                                  |
| no          | float    | Yes      | OpenWeather list[].components.no    | Nitric oxide                                     |
| no2         | float    | Yes      | OpenWeather list[].components.no2   | Nitrogen dioxide                                 |
| o3          | float    | Yes      | OpenWeather list[].components.o3    | Ozone                                            |
| so2         | float    | Yes      | OpenWeather list[].components.so2   | Sulfur dioxide                                   |
| pm2_5       | float    | Yes      | OpenWeather list[].components.pm2_5 | Fine particulate matter                          |
| pm10        | float    | Yes      | OpenWeather list[].components.pm10  | Particulate matter                               |
| nh3         | float    | Yes      | OpenWeather list[].components.nh3   | Ammonia                                          |
| ingested_at | datetime | Yes*     | Pipeline                            | Time the pipeline received/stored the record     |
|-------------|----------|----------|-------------------------------------|--------------------------------------------------|

* These fields are not returned directly by OpenWeather; they would be added by our pipeline.

4.2 Raw Data Rules
------------------
The following rules are proposed for review:
city should be a non-empty string when included in the stored raw record.
latitude should be between -90 and 90.
longitude should be between -180 and 180.
timestamp should represent the original OpenWeather observation time.
The OpenWeather dt Unix timestamp should be converted to a standard datetime representation if the team agrees to store timestamp as a datetime.
aqi should be an integer corresponding to the OpenWeather AQI value.
Pollutant measurements should be numeric values.
Missing pollutant values should remain missing rather than automatically being replaced with zero unless the team agrees on a different rule.
Pollutant units should remain consistent with the units provided by OpenWeather and should be documented in the final version of the contract.
ingested_at should represent when our pipeline processed or stored the record, rather than when OpenWeather generated the observation.


5. Gold Data Contract
The gold dataset is intended to contain cleaned/transformed data that is ready for downstream use by the application or analysis.
5.1 Proposed Gold Schema
-------------------------
|----------------|----------|----------|-----------------------------------------------------------|
| Field          | Type     | Required | Description                                               |
|----------------|----------|----------|-----------------------------------------------------------|
| city           | string   | Yes*     | City associated with the coordinates/request              |
| latitude       | float    | Yes      | Geographic latitude                                       |
| longitude      | float    | Yes      | Geographic longitude                                      |
| timestamp      | datetime | Yes      | Observation time after converting Unix timestamp          |
| aqi            | integer  | Yes      | OpenWeather Air Quality Index                             |
| co             | float    | Yes      | Carbon monoxide                                           |
| no             | float    | Yes      | Nitric oxide                                              |
| no2            | float    | Yes      | Nitrogen dioxide                                          |
| o3             | float    | Yes      | Ozone                                                     |
| so2            | float    | Yes      | Sulfur dioxide                                            |
| pm2_5          | float    | Yes      | Fine particulate matter                                   |
| pm10           | float    | Yes      | Particulate matter                                        |
| nh3            | float    | Yes      | Ammonia                                                   |
| ingested_at    | datetime | Yes*     | Time the pipeline received/stored the record              |
| transformed_at | datetime | Yes*     | Time the raw record was transformed into the gold dataset |
|----------------|----------|----------|-----------------------------------------------------------|

* Whether these fields are required or nullable should be finalized after the team agrees on missing-value handling.
The inclusion of air_quality_category and air_quality_score is a proposal and should be confirmed by the mentor/team based on the project's requirements.

6. Gold Data Transformation Rules
----------------------------------
The following are proposed rules rather than final team decisions.
7.1 Data Types
Raw pollutant measurements should be converted to the agreed numeric types.
7.2 Missing Values
The team should agree on how missing pollutant values are handled.
Possible approaches include:
Keep them as null
Exclude records that do not contain required measurements
Apply an agreed imputation strategy
No missing-value strategy should be assumed until the team agrees.
7.3 Air Quality Category
The gold dataset may contain an air_quality_category derived from the available air-quality measurements or the OpenWeather AQI.
The category definitions and thresholds should be agreed upon by the team.
7.4 Air Quality Score
The gold dataset may contain an air_quality_score.
The calculation and range of this score should be defined and agreed upon before implementation.
7.5 Deterministic Transformation
Given the same valid raw input, the transformation should produce the same gold output.

8. Proposed Pipeline Function Interfaces
-----------------------------------------
The following interfaces are proposed for discussion:
def extract(
    city: str,
    latitude: float,
    longitude: float,
    start_time: datetime,
    end_time: datetime
) -> list[dict]:
    ...

def load_raw(records: list[dict]) -> int:
    ...

def transform(records: list[dict]) -> list[dict]:
    ...

def load_gold(records: list[dict]) -> int:
    ...

These signatures are preliminary and may be changed after the team agrees on the data models and pipeline architecture.
The team should also consider whether structured models such as Pydantic models, dataclasses, or another typed representation would be preferable to list[dict].

9. Data Validation
-------------------
The pipeline should validate data before it moves between stages.
Proposed validation includes:
Raw data
Required fields are present
Correct data types are used
Latitude and longitude are valid
Timestamp can be interpreted correctly
AQI is a valid integer
Pollutant values are numeric
Unexpected or malformed API responses are handled appropriately
Gold data
Required fields are present
Data types are correct
Transformation rules have been applied
Air-quality category follows the agreed rules
Air-quality score follows the agreed calculation
Duplicate records are handled according to the agreed record-identity rule
