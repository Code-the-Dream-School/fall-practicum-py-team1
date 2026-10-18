import os
from dotenv import load_dotenv
from pydantic import json
from supabase import create_client
import json

load_dotenv()  # reads .env and sets environment variables

SUPABASE_URL = os.getenv("SUPABASE_URL")    ## Loading the Supabase URL from environment variables
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Checking for errors 

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "Missing SUPABASE_URL or SUPABASE_KEY in .env"
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
print("Connected to Supabase!")


## This file Dont call any API to get the data, it just loads the data from a local JSON file and uploads it to the Supabase database.

with open("services/pipeline/src/pipeline/load/air_pollution_data.json", "r", encoding="utf-8") as file:
    payload = json.load(file)


latitude = payload["coord"]["lat"]
longitude = payload["coord"]["lon"]

records = []  # Store database rows before uploading

for item in payload.get("list", []):
    components = item["components"]  # Get pollutant measurements

    record = {
        "dt": item["dt"],  # Observation timestamp
        "latitude": latitude,  # Location latitude
        "longitude": longitude,  # Location longitude
        "aqi": item["main"]["aqi"],  # Air quality index
        "co": components.get("co"),  # Carbon monoxide
        "no": components.get("no"),  # Nitric oxide
        "no2": components.get("no2"),  # Nitrogen dioxide
        "o3": components.get("o3"),  # Ozone
        "so2": components.get("so2"),  # Sulfur dioxide
        "pm2_5": components.get("pm2_5"),  # Fine particulate matter
        "pm10": components.get("pm10"),  # Coarse particulate matter
        "nh3": components.get("nh3"),  # Ammonia
    }

    records.append(record)  

# Upload records only when data exists
if records:
    response = (supabase.table("air_pollution_raw").upsert(records,on_conflict="dt,latitude,longitude",).execute())

    print(f"Processed {len(records)} observations.")  # Show input count
    print(f"Rows Upderted: {len(response.data)}")  # Show returned row count
else:
    print("No observations found in the JSON file.")  # Handle empty data