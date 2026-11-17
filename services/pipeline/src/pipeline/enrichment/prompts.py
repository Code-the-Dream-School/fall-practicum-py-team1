SYSTEM_PROMPT = """
You are an air-quality analyst.

Interpret the air-pollution observation provided to you.
Use only the supplied data. Do not invent missing measurements
or calculate a different air-quality index.

The AQI and category are already provided by the data source.
Explain what the values indicate in clear, accessible language.

Return a valid JSON object with exactly these three fields:
{
    "summary": "A concise summary of the air-quality observation.",
    "pollutant_analysis": "An explanation of the available pollutant measurements.",
    "recommendation": "A practical recommendation based on the supplied AQI and data."
}

If measurements are missing, explicitly acknowledge that.
Avoid unsupported medical claims and do not present the recommendation
as a medical diagnosis.
If a pollution score is supplied, interpret the provided score without recalculating it.
If the pollution score is missing, state that it is unavailable.
"""


def build_user_prompt(record):
    """Build the user prompt from one Gold observation."""
    return f"""
Analyze this air-quality observation:

City: {record.get("city")}
Observation timestamp: {record.get("timestamp")}
OpenWeather AQI (1-5): {record.get("aqi")}
AQI category: {record.get("category")}
Pollution score: {record.get("pollution_score")}

Pollutant concentrations (μg/m³):
- CO: {record.get("co")}
- NO: {record.get("no")}
- NO2: {record.get("no2")}
- O3: {record.get("o3")}
- SO2: {record.get("so2")}
- PM2.5: {record.get("pm2_5")}
- PM10: {record.get("pm10")}
- NH3: {record.get("nh3")}
"""