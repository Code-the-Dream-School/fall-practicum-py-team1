import streamlit as st
from dotenv import load_dotenv
from supabase import create_client
import os
import pandas as pd
import numpy as np
import plotly.express as px
 


def get_gold_data():

    """Fetch gold data from Supabase."""
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

    client = create_client(supabase_url, supabase_key)

    response = client.table("air_pollution_gold").select("*").execute()
    data = response.data

    if not data:
        st.warning("No data found in the gold table.")
        return pd.DataFrame()  # Return an empty DataFrame

    df = pd.DataFrame(data)
    return df



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
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # Apply the selected date range to filter the dataset.
    if isinstance(pd.date_range, tuple) and len(date_range) == 2:

        # Extract the selected start and end dates.
        start_date, end_date = date_range

        # Keep only records within the selected date range.
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
    st.subheader("📈 AQI Trend Over Time")

    # Group records by day and city.
    # Calculate the average AQI for each city on each day.
    trend = (
        df.groupby([
            pd.Grouper(key="timestamp", freq="D"),
            "city"
        ])["aqi"]
        .mean()
        .reset_index()
    )

    # Create an interactive line chart.
    # Each city is represented by a different colored line.
    fig = px.line(
        trend,
        x="timestamp",
        y="aqi",
        color="city",
        markers=True,
        title="Daily Average AQI by City",
        labels={
            "timestamp": "Date",
            "aqi": "Average AQI",
            "city": "City"
        }
    )

    # Display the AQI trend chart.
    st.plotly_chart(fig, use_container_width=True)

    

    # --------------------------------------------------------
    # 8. CITY COMPARISON
    # --------------------------------------------------------

    # Compare average pollution levels across different cities.
    st.subheader("🏙️ City Comparison")

    # Group records by city and calculate average pollutant values.
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

    # Create two columns for comparison charts.
    col1, col2 = st.columns(2)

    with col1:

        # Compare average AQI between cities.
        fig = px.bar(
            city_comparison,
            x="city",
            y="Average_AQI",
            color="city",
            title="Average AQI by City",
            labels={
                "city": "City",
                "Average_AQI": "Average AQI"
            }
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:

        # Compare average pollution scores between cities.
        fig = px.bar(
            city_comparison,
            x="city",
            y="Average_Pollution_Score",
            color="city",
            title="Average Pollution Score by City",
            labels={
                "city": "City",
                "Average_Pollution_Score": "Pollution Score"
            }
        )

        st.plotly_chart(fig, use_container_width=True)

    # Display the numerical city comparison table.
    st.subheader("City Comparison Summary")

    st.dataframe(
        city_comparison.round(2),
        use_container_width=True,
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
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --------------------------------------------------------
    # 10. POLLUTANT CONCENTRATION ANALYSIS
    # --------------------------------------------------------

    # Compare the concentrations of different air pollutants.
    st.subheader("🧪 Pollutant Concentration Analysis")

    # Define pollutant columns available in the Gold Layer.
    pollutants = [
        "pm2_5",
        "pm10",
        "no2",
        "o3",
        "co",
        "so2",
        "nh3",
        "no"
    ]

    # Calculate average pollutant concentrations by city.
    pollutant_comparison = (
        df.groupby("city")[pollutants]
        .mean()
        .reset_index()
    )

    # Convert the table into long format for visualization.
    # This allows Plotly to display each pollutant separately.
    pollutant_long = pollutant_comparison.melt(
        id_vars="city",
        var_name="Pollutant",
        value_name="Average Concentration"
    )

    # Create a grouped bar chart comparing pollutants by city.
    fig = px.bar(
        pollutant_long,
        x="Pollutant",
        y="Average Concentration",
        color="city",
        barmode="group",
        title="Average Pollutant Concentrations by City"
    )

    # Display the pollutant comparison chart.
    st.plotly_chart(fig, use_container_width=True)

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
        use_container_width=True,
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
        use_container_width=True,
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


if __name__ == "__main__":
    main()