# Air Pollutant Forecasting Model

This directory contains the predictive modeling subproject for forecasting air-pollution concentrations from the pipeline's cleaned gold dataset. The model stack is built around LightGBM regression models trained on time-aware features and lagged pollutant values.

## Purpose

The project trains machine learning models to predict future pollutant levels for each pollutant tracked in the dataset, including:

- CO
- NO
- NO2
- O3
- SO2
- PM2.5
- PM10
- NH3

The modeling workflow uses historical air-quality records, location metadata, temporal patterns, and recent pollutant behavior to generate short-horizon forecasts.

## Directory structure

- `config.py` - model configuration and model artifact paths.
- `src/train.py` - training pipeline, LightGBM training loop, and model serialization.
- `src/preprocess.py` - feature engineering for time, periodicity, and lagged pollutant values.
- `src/predict.py` - inference entry point for loading a saved model and generating predictions.
- `src/io.py` - utilities for reading the gold dataset and loading saved model metadata.
- `models/` - trained LightGBM model files and metadata JSON for each pollutant.
- `testing/` - sample parquet data used for validation and prediction checks.
- `eda.ipynb` - exploratory analysis notebook.

## Modeling approach

The training workflow is designed around a time-series forecasting setup:

1. Load the cleaned gold data from Supabase.
2. Select the useful feature set such as city, coordinates, timestamp, AQI, pollutant readings, and time-based fields.
3. Preprocess the data by:
   - encoding categorical time fields
   - extracting hour/day/month information
   - adding sin/cos periodic features
   - creating lagged pollutant values at 1, 3, 8, and 24 hours
   - adding rolling mean/min/max features over the previous 24 hours
   - creating a 24-hour-ahead target for each pollutant
4. Train a LightGBM regressor for each pollutant target.
5. Save the trained model as a `.txt` file plus metadata in JSON.

The target is defined as the future pollutant value 24 hours ahead (`<pollutant>_target`).

## Key feature engineering

The preprocessing pipeline includes several useful temporal and lag-based features:

- `time_of_day`
- `day_of_week`
- `hour`, `day`, `month`
- sine/cosine periodic encodings for time components
- pollutant lag features: `*_lag1`, `*_lag3`, `*_lag8`, `*_lag24`
- rolling statistics: `*_mean24`, `*_max24`, `*_min24`
- target values representing future pollutant measurements

This feature set is intended to capture seasonality, diurnal cycles, and recent pollution trends that influence future values.

## Training

Training is orchestrated by the script in `src/train.py`.

### Typical workflow

From the project root, include the source path and run the training module:

```bash
export PYTHONPATH=services/pipeline/src
python -m model.src.train
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH = "services\pipeline\src"
python -m model.src.train
```

The script will:

- load the gold data from the configured database
- filter to a clean post-2025-04-01 time window
- preprocess the data
- train one model per pollutant target
- save each model and JSON metadata in `models/`

## Prediction

Prediction is handled by `src/predict.py`.

```bash
export PYTHONPATH=services/pipeline/src
python -m model.src.predict
```

This loads a saved model for a pollutant, re-applies the preprocessing pipeline to the input dataframe, and returns model predictions. If the model has not yet been trained for the requested pollutant, it will trigger training automatically.

## Model artifacts

Trained models are stored under:

- `models/*.txt` - LightGBM model files
- `models/*_meta.json` - model metadata with feature lists and training context

Each metadata JSON file includes:

- pollutant name
- saved timestamp
- LightGBM version
- model features
- training parameters
- row count

## Data requirements

This subproject expects the upstream pipeline to provide a valid gold dataset in Supabase. The data should contain the fields defined by the shared pipeline configuration and include at least:

- `city`
- `latitude`
- `longitude`
- `timestamp`
- `aqi`
- pollutant columns
- time-of-day and day-of-week summary fields

## Environment configuration

Before training or predicting, configure the environment variables for the project, especially the Supabase connection used by the pipeline and model layers:

- `SUPABASE_URL`
- `SUPABASE_KEY`

The repository also expects the project-level Python path to include `services/pipeline/src` so that imports resolve correctly.

## Dependencies

This subproject depends on:

- pandas
- numpy
- scikit-learn
- lightgbm
- python-dotenv
- supabase

## Notes

This model directory is a focused forecasting component of the broader air-pollution pipeline. It is designed to turn transformed, time-aware measurements into a reusable predictive model for each pollutant category, and it is intended to be extended as more features and forecast horizons are added.