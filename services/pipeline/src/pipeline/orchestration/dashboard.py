from sqlalchemy import event
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client
import os
import pandas as pd
import numpy as np
import plotly.express as px
 

@st.cache_data(ttl=1800)
def get_gold_data():

    """Fetch gold data from Supabase."""
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

    client = create_client(supabase_url, supabase_key)

    # Store all retrieved records here.
    all_data = []

    # Supabase range uses zero-based, inclusive indexes.
    batch_size = 1000
    start = 0

    while True:

        response = (
            client.table("air_pollution_gold")
            .select("*")
            .range(start, start + batch_size - 1)
            .execute()
        )

        batch = response.data or []

        # Add the current batch to the complete dataset.
        all_data.extend(batch)

        # Stop when the returned batch contains fewer records
        # than the requested batch size.
        if len(batch) < batch_size:
            break

        # Move to the next batch.
        start += batch_size

    if not all_data:
        st.warning("No data found in the gold table.")
        return pd.DataFrame()

    return pd.DataFrame(all_data)


@st.cache_data(ttl=1800)
def get_air_pollution_enrichment():

    """Fetch enrichment data from Supabase."""
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

    client = create_client(supabase_url, supabase_key)

    # Store all retrieved records here.
    all_enriched_data = []

    # Supabase range uses zero-based, inclusive indexes.
    batch_size = 1000
    start = 0

    while True:

        response = (
            client.table("air_pollution_enrichment")
            .select("*")
            .range(start, start + batch_size - 1)
            .execute()
        )

        batch = response.data or []

        # Add the current batch to the complete dataset.
        all_enriched_data.extend(batch)

        # Stop when the returned batch contains fewer records
        # than the requested batch size.
        if len(batch) < batch_size:
            break

        # Move to the next batch.
        start += batch_size

    if not all_enriched_data:
        st.warning("No data found in the enrichment table.")
        return pd.DataFrame()

    return pd.DataFrame(all_enriched_data)

 #enrichment_data = get_air_pollution_enrichment()

#print(enrichment_data.columns.tolist())
#print(enrichment_data.head(3).to_string())



@st.cache_data(ttl=1800)
def match_daily_enrichment(trend, enrichment_data):
    """
    Match one successful LLM enrichment record
    to each daily AQI point.

    Selection priority:
    1. Closest timestamp to 12 PM UTC.
    2. Prefer later timestamp when equally close.
    3. Same-day records only.

    If no enrichment exists for a city on a given day,
    display 'No enrichment records available'.
    """

    trend = trend.copy()
    enrichment_data = enrichment_data.copy()

    # -------------------------------------------------
    # 1. NORMALIZE TREND DATA
    # -------------------------------------------------

    trend["timestamp"] = pd.to_datetime(
        trend["timestamp"],
        errors="coerce",
        utc=True
    )
    trend = trend.dropna(subset=["timestamp"]).copy()

    for column in ["latitude", "longitude"]:
        trend[column] = pd.to_numeric(
            trend[column],
            errors="coerce"
        )

    # -------------------------------------------------
    # 2. NORMALIZE ENRICHMENT DATA
    # -------------------------------------------------

    enrichment_data["timestamp"] = pd.to_datetime(
        enrichment_data["timestamp"],
        errors="coerce",
        utc=True
    )

    for column in ["latitude", "longitude"]:
        enrichment_data[column] = pd.to_numeric(
            enrichment_data[column],
            errors="coerce"
        )

    # -------------------------------------------------
    # 3. KEEP SUCCESSFUL ENRICHMENT RECORDS
    # -------------------------------------------------

    enrichment_data = enrichment_data[
        enrichment_data["status"] == "success"
    ].copy()

    enrichment_data = enrichment_data.dropna(
        subset=[
            "timestamp",
            "latitude",
            "longitude"
        ]
    )

    # -------------------------------------------------
    # 4. EXTRACT UTC DATES
    # -------------------------------------------------

    trend["date"] = trend["timestamp"].dt.date

    enrichment_data["date"] = (
        enrichment_data["timestamp"].dt.date
    )

    # -------------------------------------------------
    # 5. INITIALIZE ENRICHMENT COLUMNS
    # -------------------------------------------------

    trend["summary"] = None
    trend["recommendation"] = None
    trend["pollutant_analysis"] = None

    trend["enrichment_status"] = (
        "No enrichment records available"
    )

    # -------------------------------------------------
    # 6. MATCH EACH CITY AND DAY
    # -------------------------------------------------

    for index, row in trend.iterrows():

        # Find successful records for the same city
        # location and UTC calendar date.

        candidates = enrichment_data[
            (enrichment_data["latitude"] == row["latitude"]) &
            (enrichment_data["longitude"] == row["longitude"]) &
            (enrichment_data["date"] == row["date"])
        ].copy()

        # No enrichment records for this city and day.
        if candidates.empty:
            trend.at[index, "enrichment_status"] = (
                "No enrichment records available"
            )
            continue

        # -------------------------------------------------
        # 7. FIND RECORD CLOSEST TO 12 PM UTC
        # -------------------------------------------------

        noon = pd.Timestamp(
            str(row["date"]) + " 12:00:00",
            tz="UTC"
        )

        candidates["time_difference"] = (
            candidates["timestamp"] - noon
        ).abs()

        # Closest timestamp first.
        # Later timestamp wins when equally close.

        candidates = candidates.sort_values(
            ["time_difference", "timestamp"],
            ascending=[True, False]
        )

        # -------------------------------------------------
        # 8. SELECT BEST MATCH
        # -------------------------------------------------

        selected = candidates.iloc[0]

        result = selected["result"]

        # Check that the result contains a dictionary.
        if not isinstance(result, dict):

            trend.at[index, "enrichment_status"] = (
                "Enrichment record found, but result is invalid"
            )

            continue

        # -------------------------------------------------
        # 9. EXTRACT LLM-GENERATED INSIGHTS
        # -------------------------------------------------

        trend.at[index, "summary"] = (
            result.get("summary")
        )

        trend.at[index, "recommendation"] = (
            result.get("recommendation")
        )

        trend.at[index, "pollutant_analysis"] = (
            result.get("pollutant_analysis")
        )

        trend.at[index, "enrichment_status"] = (
            "Enrichment available"
        )

    # -------------------------------------------------
    # 10. RETURN MATCHED DATA
    # -------------------------------------------------

    return trend





# ---------------------------------------------------------
# DATE FILTERING FUNCTION
# ---------------------------------------------------------

def filter_by_date_range(df, date_range):
    """Filter records using the selected date range."""

    if isinstance(date_range, tuple) and len(date_range) == 2:

        start_date, end_date = date_range

        df = df[
            (df["timestamp"].dt.date >= start_date) &
            (df["timestamp"].dt.date <= end_date)
        ]

    return df


def calculate_dashboard_metrics(df):
    """Calculate the main dashboard performance metrics."""

    return {
        "average_aqi": df["aqi"].mean(),
        "maximum_aqi": df["aqi"].max(),
        "average_pm25": df["pm2_5"].mean(),
        "average_pm10": df["pm10"].mean(),
        "average_o3": df["o3"].mean(),
        "average_pollution_score": df["pollution_score"].mean(),
        "total_records": len(df),
        "monitored_cities": df["city"].nunique()
    }


#-----------------------------------------------------------------
# Dashboard polish and extra charts
#------------------------------------------------------------------


def display_monthly_aqi_trend(df):
    """
    Display monthly average AQI trends for all cities
    across the entire available dataset.

    Uses a copy of the original DataFrame so that
    existing dashboard data and filters are unaffected.
    """

    # -------------------------------------------------
    # 1. COPY THE ENTIRE DATASET
    # -------------------------------------------------

    monthly_df = df.copy()

    # -------------------------------------------------
    # 2. PREPROCESS DATA
    # -------------------------------------------------

    monthly_df["timestamp"] = pd.to_datetime(
        monthly_df["timestamp"],
        errors="coerce",
        utc=True
    )

    monthly_df["aqi"] = pd.to_numeric(
        monthly_df["aqi"],
        errors="coerce"
    )

    monthly_df = monthly_df.dropna(
        subset=["timestamp", "aqi", "city"]
    )

    if monthly_df.empty:
        st.warning("No valid AQI records available for monthly analysis.")
        return

    # -------------------------------------------------
    # 3. GROUP DATA BY MONTH AND CITY
    # -------------------------------------------------

    monthly_trend = (
        monthly_df.groupby([
            pd.Grouper(key="timestamp", freq="MS"),
            "city"
        ])["aqi"]
        .mean()
        .reset_index()
    )

    # -------------------------------------------------
    # 4. DISPLAY MONTHLY AQI TREND
    # -------------------------------------------------

    st.subheader("📈 Monthly Average AQI Trend")

    fig = px.line(
        monthly_trend,
        x="timestamp",
        y="aqi",
        color="city",
        markers=True,
        title="Monthly Average AQI by City",
        labels={
            "timestamp": "Month",
            "aqi": "Monthly Average AQI",
            "city": "City"
        }
    )

    fig.update_xaxes(
        tickformat="%b %Y",
        title="Month"
    )

    fig.update_yaxes(
        title="Average AQI"
    )

    fig.update_layout(
        hovermode="x unified",
        legend_title="City"
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )


def display_monthly_aqi_heatmap(df):
    """
    Display a heatmap showing monthly average AQI
    across all monitored cities.

    Uses the complete dataset without modifying
    the original DataFrame or dashboard filters.
    """

    # -------------------------------------------------
    # 1. COPY THE COMPLETE DATASET
    # -------------------------------------------------

    heatmap_df = df.copy()

    # -------------------------------------------------
    # 2. DATA PREPROCESSING
    # -------------------------------------------------

    heatmap_df["timestamp"] = pd.to_datetime(
        heatmap_df["timestamp"],
        errors="coerce",
        utc=True
    )

    heatmap_df["aqi"] = pd.to_numeric(
        heatmap_df["aqi"],
        errors="coerce"
    )

    heatmap_df = heatmap_df.dropna(
        subset=["timestamp", "aqi", "city"]
    )

    if heatmap_df.empty:
        st.warning("No valid AQI records available for heatmap.")
        return

    # -------------------------------------------------
    # 3. EXTRACT MONTH AND YEAR
    # -------------------------------------------------

    heatmap_df["month"] = (
        heatmap_df["timestamp"].dt.strftime("%Y-%m")
    )

    # -------------------------------------------------
    # 4. CALCULATE MONTHLY AVERAGE AQI BY CITY
    # -------------------------------------------------

    monthly_aqi = (
        heatmap_df.groupby(["city", "month"])["aqi"]
        .mean()
        .reset_index()
    )

    # -------------------------------------------------
    # 5. CONVERT DATA INTO HEATMAP FORMAT
    # -------------------------------------------------

    heatmap_data = monthly_aqi.pivot(
        index="city",
        columns="month",
        values="aqi"
    )

    heatmap_data = heatmap_data.sort_index(axis=1)

    # -------------------------------------------------
    # 6. DISPLAY HEATMAP
    # -------------------------------------------------

    st.subheader("🌡️ Monthly AQI Heatmap")

    fig = px.imshow(
        heatmap_data,
        labels={
            "x": "Month",
            "y": "City",
            "color": "Average AQI"
        },
        x=heatmap_data.columns,
        y=heatmap_data.index,
        color_continuous_scale=[
            [0.0, "green"],
            [0.25, "yellow"],
            [0.50, "orange"],
            [0.75, "red"],
            [1.0, "purple"]
        ],
        aspect="auto",
        text_auto=".1f",
        title="Monthly Average AQI Across Cities"
    )

    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="City",
        coloraxis_colorbar_title="Average AQI"
    )

    st.plotly_chart(
        fig,
        width="stretch"
    )


def make_dashboard():
    """
    ============================================================
                    AIR POLLUTION DASHBOARD
    ============================================================

    Purpose:
        Creates an interactive Streamlit dashboard to visualize
        and analyze air pollution data retrieved from the
        Supabase Gold Layer.

    Data Source:
        Supabase table: air_pollution_gold

    Dashboard Features:
        1. Air quality summary metrics (KPIs).
        2. City and date filters.
        3. AQI trends over time.
        4. City air quality comparison.
        5. Pollution category distribution.
        6. Pollutant concentration comparison.
        7. Daily AQI statistics.
        8. Detailed air pollution records.
        9. CSV data download.

    Data Columns Used:
        city, timestamp, aqi, pm2_5, pm10, o3, no2,
        co, so2, nh3, category, aqi_rolling_avg,
        daily_max, daily_min, daily_range, pollution_score.

    Returns:
        None. Displays the dashboard using Streamlit.

    To Run : streamlit run services/pipeline/src/pipeline/orchestration/dashboard.py (Path can vary based on your project structure)
            then follow the link in the terminal to view the dashboard in your browser.
            e.g.
            Local URL: http://localhost:8501
            Network URL: http://192.168.12.151:8501

    ============================================================
    """

    # --------------------------------------------------------
    # 1. PAGE CONFIGURATION
    # --------------------------------------------------------

    # Configure the dashboard's browser tab title, icon, and layout.
    st.set_page_config(
        page_title="City Air Tracker Dashboard",
        page_icon="🌍",
        layout="wide"
    )

    # Display the main dashboard heading.
    st.title("🌍 City Air Tracker Dashboard")

    # Provide a short description of the dashboard's purpose.
    st.caption(
        "Monitoring and analyzing air quality across "
        "different cities using Gold Layer data."
    )

    # --------------------------------------------------------
    # 2. FETCH DATA FROM THE GOLD LAYER
    # --------------------------------------------------------

    # Retrieve air pollution records from the existing
    # get_gold_data() function, which connects to Supabase.
    try:
        with st.spinner("Loading air pollution data..."):
            gold_data = get_gold_data()

    # Handle errors such as database connection failures
    # or missing environment variables.
    except Exception as e:
        st.error("Failed to retrieve data from Supabase.")
        st.error(str(e))
        return

    # Check whether the Gold Layer table contains records.
    if gold_data is None or gold_data.empty:
        st.info("No air pollution data available yet.")
        return
    # Fetch enrichment data from Supabase
    try:
        with st.spinner("Loading AI enrichment data..."):
            enrichment_data = get_air_pollution_enrichment()

    except Exception as e:
        st.error("Failed to retrieve enrichment data from Supabase.")
        st.error(str(e))
        return
    
    # Create a copy so that dashboard transformations
    # do not modify the original retrieved DataFrame.
    df = gold_data.copy()

    # --------------------------------------------------------
    # 3. DATA PREPROCESSING
    # --------------------------------------------------------

    # Convert timestamp strings into Pandas datetime objects.
    # This allows date filtering and time-series analysis.
    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
        utc=True
    )

    # Convert pollutant and AQI columns to numeric values.
    # Invalid values are converted to NaN.
    numeric_columns = [
        "aqi",
        "co",
        "no",
        "no2",
        "o3",
        "so2",
        "pm2_5",
        "pm10",
        "nh3",
        "aqi_rolling_avg",
        "daily_max",
        "daily_min",
        "daily_range",
        "pollution_score"
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    # Remove records without valid timestamps.
    df = df.dropna(subset=["timestamp"])

    # Stop execution if no valid records remain.
    if df.empty:
        st.warning("No valid air pollution records found.")
        return

    # --------------------------------------------------------
    # 4. SIDEBAR FILTERS
    # --------------------------------------------------------

    # Add a filter section to the dashboard sidebar.
    st.sidebar.header("🔎 Dashboard Filters")

    # Extract all unique city names from the dataset.
    cities = sorted(df["city"].dropna().unique())

    # Allow users to select one or multiple cities.
    # All cities are selected by default.
    selected_cities = st.sidebar.multiselect(
        "Select Cities",
        cities,
        default=cities
    )

    # Filter records based on the selected cities.
    df = df[df["city"].isin(selected_cities)].copy()

    # Display a message if no cities were selected.
    if df.empty:
        st.warning("Please select at least one city.")
        return

    # --------------------------------------------------------
    # 5. DATE RANGE FILTER
    # --------------------------------------------------------

    # Find the earliest and latest dates available in the Gold dataset.
    min_date = df["timestamp"].min().date()
    max_date = df["timestamp"].max().date()

    # Display a date picker in the sidebar.
    # min_value and max_value prevent users from selecting dates
    # outside the available date range in the Gold database.
    start_date = st.sidebar.date_input(
        "Select Start Date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key="start_date"
    )

    # Select the end date.
    end_date = st.sidebar.date_input(
        "Select End Date",
        value=max_date,
        min_value=start_date,
        max_value=max_date,
        key="end_date"
    )

    # Filter records using the selected start and end dates.
    df = df[
        (df["timestamp"].dt.date >= start_date) &
        (df["timestamp"].dt.date <= end_date)
    ]

    # Check whether records remain after filtering.
    if df.empty:
        st.warning("No records found for the selected date range.")
        return

    # --------------------------------------------------------
    # 6. KEY PERFORMANCE INDICATORS (KPIs)
    # --------------------------------------------------------

    # Display the main air quality summary section.
    st.subheader("📊 Air Quality Overview")

    # Create four columns to organize summary metrics.
    col1, col2, col3, col4 = st.columns(4)

    # Calculate the average AQI across filtered records.
    col1.metric(
        "Average AQI",
        f"{df['aqi'].mean():.1f}"
    )

    # Display the highest AQI value in the filtered dataset.
    col2.metric(
        "Maximum AQI",
        f"{df['aqi'].max():.0f}"
    )

    # Calculate the average PM2.5 concentration.
    col3.metric(
        "Average PM2.5",
        f"{df['pm2_5'].mean():.2f}"
    )

    # Calculate the average pollution score.
    col4.metric(
        "Pollution Score",
        f"{df['pollution_score'].mean():.1f}"
    )

    # Create another row of summary metrics.
    col5, col6, col7, col8 = st.columns(4)

    # Calculate the average PM10 concentration.
    col5.metric(
        "Average PM10",
        f"{df['pm10'].mean():.2f}"
    )

    # Calculate the average ozone concentration.
    col6.metric(
        "Average O3",
        f"{df['o3'].mean():.2f}"
    )

    # Display the total number of records after filtering.
    col7.metric(
        "Total Records",
        f"{len(df):,}"
    )

    # Display the number of cities represented in the filtered data.
    col8.metric(
        "Cities Monitored",
        f"{df['city'].nunique()}"
    )

    st.divider()

    
    # --------------------------------------------------------
    # 7. AQI TREND OVER TIME
    # --------------------------------------------------------

    # This section shows how air quality changes over time.
    # Group records by day and city.
    # Calculate the average AQI for each city on each day.
    # Determine aggregation frequency based on selected date range

    # Calculate the selected date range.
    selected_days = (end_date - start_date).days

    # Automatically determine AQI aggregation frequency.
    if selected_days <= 60:
        aggregation_frequency = "D"
        aggregation_label = "Daily"

    elif selected_days <= 365:
        aggregation_frequency = "W"
        aggregation_label = "Weekly"

    elif selected_days <= 1095:
        aggregation_frequency = "MS"
        aggregation_label = "Monthly"

    else:
        aggregation_frequency = "QS"
        aggregation_label = "Quarterly"
    


    trend = (
    df.groupby([
        pd.Grouper(
            key="timestamp",
            freq=aggregation_frequency
        ),
        "city",
        "latitude",
        "longitude"
    ])["aqi"]
    .mean()
    .reset_index()
    )
    st.subheader(f"📈 {aggregation_label} AQI Trend Over Time")

    # Match the correct same-day LLM enrichment
    # to each daily AQI point.
    if aggregation_frequency == "D":
        trend = match_daily_enrichment(
            trend,
            enrichment_data
        )
    else:
        trend["summary"] = None
        trend["recommendation"] = None
        trend["pollutant_analysis"] = None
        trend["enrichment_status"] = "Aggregated period"

    # Debugging information.
    # print("MATCHED TREND DATA:")
    # print(trend[["city","timestamp","aqi","enrichment_status","summary","recommendation","pollutant_analysis"]].head(20).to_string())

    # print("TREND COLUMNS:")
    # print(trend.columns.tolist())

    # Create an interactive line chart.
    # Each city is represented by a different colored line.
    fig = px.line(
        trend,
        x="timestamp",
        y="aqi",
        color="city",
        markers=True,
        title=f"{aggregation_label} Average AQI by City",
        custom_data=[
            "enrichment_status",
            "summary",
            "recommendation",
            "pollutant_analysis"
        ],
        labels={
            "timestamp": "Date",
            "aqi": "Average AQI",
            "city": "City"
        },
        hover_data={
            "enrichment_status": False,
            "summary": False,
            "recommendation": False,
            "pollutant_analysis": False
        }
    )

    # Configure the chart hover information.
    fig.update_traces(
        hovertemplate=(
            "<b>%{fullData.name}</b><br>"
            "Date: %{x|%Y-%m-%d}<br>"
            "AQI: %{y:.2f}<br>"
            "Enrichment Status: %{customdata[0]}"
            "<extra></extra>"
        )
    )

    # Display the chart and capture click selections.
    event = st.plotly_chart(
        fig,
        width="stretch",
        on_select="rerun",
        selection_mode="points",
        key="aqi_trend_chart"
    )

    # --------------------------------------------------------
    # DISPLAY FULL ENRICHMENT WHEN A CHART POINT IS CLICKED
    # --------------------------------------------------------
    if aggregation_frequency == "D":
        if event and event.selection and event.selection.points:

            selected_point = event.selection.points[0]

            # Get the selected point's city and date.
            selected_city = selected_point["curve_number"]
            selected_timestamp = selected_point["x"]

            # Identify the selected city from the chart trace.
            city_name = fig.data[selected_city].name

            # Find the corresponding row using city and timestamp.
            selected_rows = trend[
                (trend["city"] == city_name) &
                (
                    trend["timestamp"] ==
                    pd.to_datetime(selected_timestamp, utc=True)
                )
            ]

            if not selected_rows.empty:

                selected_row = selected_rows.iloc[0]

                st.divider()
                st.subheader("🤖 Daily AI Enrichment Details")

                st.write(f"**City:** {selected_row['city']}")

                st.write(
                    f"**Date:** "
                    f"{selected_row['timestamp'].strftime('%Y-%m-%d')}"
                )

                st.write(f"**AQI:** {selected_row['aqi']:.2f}")

                st.write(
                    f"**Status:** {selected_row['enrichment_status']}"
                )

                if selected_row["enrichment_status"] == "Enrichment available":

                    st.markdown("### Summary")
                    st.write(selected_row["summary"])

                    st.markdown("### Recommendation")
                    st.write(selected_row["recommendation"])

                    st.markdown("### Pollutant Analysis")
                    st.write(selected_row["pollutant_analysis"])

                else:
                    st.info(
                        "No enrichment records available "
                        "for this city and date."
                    )

        else:
            st.caption(
                "Click a point on the AQI chart to view its full AI enrichment."
            )

    # --------------------------------------------------------
    # Dashboard polish and extra charts. MONTHLY AVERAGE AQI TREND
    # --------------------------------------------------------

    # display_monthly_aqi_trend(gold_data)

    # st.divider()
    
    # --------------------------------------------------------
    # Dashboard polish and extra charts. MONTHLY AQI HEATMAP
    # --------------------------------------------------------

    display_monthly_aqi_heatmap(gold_data)

    st.divider()


    # --------------------------------------------------------
    # 8. CITY COMPARISON
    # --------------------------------------------------------

    st.subheader("🏙️ City Comparison")

    city_comparison = (
        df.groupby("city")
        .agg(
            Average_AQI=("aqi", "mean"),
            Average_PM25=("pm2_5", "mean"),
            Average_PM10=("pm10", "mean"),
            Average_O3=("o3", "mean"),
            Average_Pollution_Score=("pollution_score", "mean")
        )
        .reset_index()
    )

    # Keep both charts side by side
    col1, col2 = st.columns(2)

    # --------------------------------------------------------
    # LEFT CHART: AVERAGE AQI
    # --------------------------------------------------------

    with col1:

        fig = px.bar(
            city_comparison.sort_values(
                "Average_AQI",
                ascending=True
            ),
            x="Average_AQI",
            y="city",
            orientation="h",
            color="Average_AQI",
            text="Average_AQI",
            color_continuous_scale=[
                [0.0, "green"],
                [0.5, "yellow"],
                [1.0, "red"]
            ],
            title="Average AQI by City",
            labels={
                "city": "City",
                "Average_AQI": "Average AQI"
            }
        )

        fig.update_traces(
            texttemplate="%{x:.2f}",
            textposition="outside",
            cliponaxis=False
        )

        fig.update_layout(
            xaxis_title="Average AQI",
            yaxis_title="City",
            bargap=0.5,
            coloraxis_showscale=False,
            margin=dict(r=60)
        )

        st.plotly_chart(fig, width="stretch")


    # --------------------------------------------------------
    # RIGHT CHART: AVERAGE POLLUTION SCORE
    # --------------------------------------------------------

    with col2:

        fig = px.bar(
            city_comparison.sort_values(
                "Average_Pollution_Score",
                ascending=True
            ),
            x="Average_Pollution_Score",
            y="city",
            orientation="h",
            color="Average_Pollution_Score",
            text="Average_Pollution_Score",
            color_continuous_scale=[
                [0.0, "green"],
                [0.5, "yellow"],
                [1.0, "red"]
            ],
            title="Average Pollution Score by City",
            labels={
                "city": "City",
                "Average_Pollution_Score": "Pollution Score"
            }
        )

        fig.update_traces(
            texttemplate="%{x:.2f}",
            textposition="outside",
            cliponaxis=False
        )

        fig.update_layout(
            xaxis_title="Pollution Score",
            yaxis_title="City",
            bargap=0.5,
            coloraxis_showscale=False,
            margin=dict(r=60)
        )

        st.plotly_chart(fig, width="stretch")


    # --------------------------------------------------------
    # CITY COMPARISON SUMMARY
    # --------------------------------------------------------

    st.subheader("City Comparison Summary")

    st.dataframe(
        city_comparison.round(2),
        width="stretch",
        hide_index=True
    )

    st.divider()




    # --------------------------------------------------------
    # 9. POLLUTION CATEGORY DISTRIBUTION
    # --------------------------------------------------------

    # Analyze how many records belong to each air quality category.
    st.subheader("🌫️ Pollution Category Distribution")

    # Count records for each pollution category.
    category_counts = (
        df["category"]
        .value_counts()
        .reset_index()
    )

    # Rename columns to make chart labels more readable.
    category_counts.columns = ["Category", "Records"]

    # Create a donut chart showing category distribution.
    fig = px.pie(
        category_counts,
        names="Category",
        values="Records",
        hole=0.4,
        title="Distribution of Air Quality Categories"
    )       

    # Display the category distribution chart.
    st.plotly_chart(fig, width="stretch")

    st.divider()

    # --------------------------------------------------------
    # 10. POLLUTANT CONCENTRATION ANALYSIS
    # --------------------------------------------------------

    # Compare the concentrations of different air pollutants.
    st.subheader("🧪 Pollutant Concentration Analysis")

    # Define pollutant columns available in the Gold Layer.
    pollutants = {
    "Fine Particulate Matter PM2.5": "pm2_5",
    "Coarse Particulate Matter PM10": "pm10",
    "Nitrogen Dioxide NO2": "no2",
    "Ozone O3": "o3",
    "Carbon Monoxide CO": "co",
    "Sulfur Dioxide SO2": "so2",
    "Ammonia NH3": "nh3",
    "Nitric Oxide NO": "no"
    }

    # Keep only pollutant columns available in the dataset.
    available_pollutants = {
        name: column
        for name, column in pollutants.items()
        if column in df.columns
    }

    if not available_pollutants:
        st.warning("No pollutant concentration data available.")


    else:

        # Allow users to select one pollutant.

        selected_pollutant = st.selectbox(
            "Select a pollutant",
        options=list(available_pollutants.keys()),
        key="pollutant_selector"
        )

        selected_column = available_pollutants[selected_pollutant]

        # Calculate average concentration by city.
        pollutant_data = (
            df.groupby("city")[selected_column]
            .mean()
            .reset_index()
        )

        pollutant_data = pollutant_data.dropna(
        subset=[selected_column]
        )

        # Create a chart for the selected pollutant only.
        fig = px.bar(
            pollutant_data,
            x="city",
            y=selected_column,
            color="city",
            title=f"Average {selected_pollutant} Concentration by City",
            labels={
                "city": "City",
                selected_column: f"{selected_pollutant} Concentration"
            }
        )


        
        fig.update_layout(
            xaxis_title="City",
            yaxis_title=f"{selected_pollutant} Concentration"
        )

        st.plotly_chart(
            fig,
            width="stretch"
        )

    st.divider()



    # --------------------------------------------------------
    # 11. DAILY AQI STATISTICS
    # --------------------------------------------------------

    # Analyze daily minimum, maximum, and range of AQI values.
    st.subheader("📅 Daily AQI Statistics")

    # Group records by city and calculate daily AQI statistics.
    daily_stats = (
        df.groupby("city")
        .agg(
            Daily_Max=("daily_max", "max"),
            Daily_Min=("daily_min", "min"),
            Average_Daily_Range=("daily_range", "mean")
        )
        .reset_index()
    )

    # Display daily AQI statistics in a table.
    st.dataframe(
        daily_stats.round(2),
        width="stretch",
        hide_index=True
    )

    # --------------------------------------------------------
    # 12. DETAILED AIR POLLUTION RECORDS
    # --------------------------------------------------------

    # Display the complete filtered dataset in a table.
    st.subheader("📋 Detailed Air Pollution Records")

    # Select relevant columns for the detailed records table.
    # Only include columns that exist in the DataFrame.
    display_columns = [
        "city",
        "timestamp",
        "aqi",
        "category",
        "pm2_5",
        "pm10",
        "o3",
        "no2",
        "co",
        "so2",
        "nh3",
        "aqi_rolling_avg",
        "daily_max",
        "daily_min",
        "daily_range",
        "pollution_score"
    ]

    # Keep only columns that are present in the dataset.
    display_columns = [
        col for col in display_columns
        if col in df.columns
    ]

    # Sort records by timestamp so the newest records appear first.
    # Display the records in an interactive Streamlit table.
    st.dataframe(
        df[display_columns].sort_values(
            "timestamp",
            ascending=False
        ),
        width="stretch",
        hide_index=True
    )

    # --------------------------------------------------------
    # 13. DOWNLOAD FILTERED DATA
    # --------------------------------------------------------

    # Allow users to download the currently filtered dataset.
    # Convert the DataFrame into CSV format before downloading.
    st.download_button(
        label="⬇️ Download Air Pollution Data",
        data=df.to_csv(index=False),
        file_name="air_pollution_data.csv",
        mime="text/csv"
    )



def main() -> None:

    make_dashboard()

print("Matching function loaded successfully:",
      callable(match_daily_enrichment))

if __name__ == "__main__":
    main()