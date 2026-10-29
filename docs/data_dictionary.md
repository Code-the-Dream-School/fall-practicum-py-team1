| **Field name** | **Description** | **Data type** | **Unit / format** | **Source or transformation rule** | **Required?** |
|---|---|---|---|---|---|
| city | City where the air quality observation was recorded | text | City name | Location metadata | Yes |
| latitude | Latitude of the observation location | double precision | Decimal degrees | Location metadata | Yes |
| longitude | Longitude of the observation location | double precision | Decimal degrees | Location metadata | Yes |
| timestamp | Time when the air quality observation was recorded | timestamp with time zone | UTC timestamp | Raw observation timestamp converted to a timestamp | Yes |
| transformed_at | Time when the record was transformed into Gold format | timestamp with time zone | UTC timestamp | Generated during transformation | Yes |
| aqi | OpenWeather Air Quality Index value | integer | Scale 1–5 | Raw AQI value | Yes |
| co | Carbon monoxide concentration | double precision | µg/m³ | Raw pollutant measurement | No |
| no | Nitrogen monoxide concentration | double precision | µg/m³ | Raw pollutant measurement | No |
| no2 | Nitrogen dioxide concentration | double precision | µg/m³ | Raw pollutant measurement | No |
| o3 | Ozone concentration | double precision | µg/m³ | Raw pollutant measurement | No |
| so2 | Sulfur dioxide concentration | double precision | µg/m³ | Raw pollutant measurement | No |
| pm2_5 | Fine particulate matter concentration | double precision | µg/m³ | Raw pollutant measurement | No |
| pm10 | Coarse particulate matter concentration | double precision | µg/m³ | Raw pollutant measurement | No |
| nh3 | Ammonia concentration | double precision | µg/m³ | Raw pollutant measurement | No |
| category | Human-readable air quality category | text | Good, Fair, Moderate, Poor, Very Poor | Maps AQI values 1–5 to category labels | No |
| time_of_day | Period of the day when the observation occurred | text | Morning, Afternoon, Evening, Night | Derived from local observation time | No |
| day_of_week | Weekday of the observation | text | Full weekday name | Derived from local timestamp | No |
| month | Month of the observation | text | Full month name | Derived from local timestamp | No |
| year | Year of the observation | integer | Four-digit year | Derived from local timestamp | No |
| aqi_rolling_avg | Average AQI across the current and up to two previous observations at the same location | double precision | AQI points | Three-observation rolling mean, rounded to two decimals | No |
| daily_max | Highest AQI observed at the location on that local calendar day | integer | AQI points | Daily maximum grouped by location and local date | No |
| daily_min | Lowest AQI observed at the location on that local calendar day | integer | AQI points | Daily minimum grouped by location and local date | No |
| daily_range | Difference between the daily maximum and minimum AQI | integer | AQI points | daily_max - daily_min | No |
| pollution_score | Custom score representing the severity of the OpenWeather AQI value | numeric | 0–100, rounded to two decimals | `((aqi - 1) / 4) * 100` | No |