import streamlit as st
import ee
import pandas as pd
from datetime import datetime, timedelta
import os
import time  # Import time for timing the analysis and download
import json

# Access the secret from environment variables
credentials = os.getenv("EE_AUTHENTICATION")

if credentials is None:
    st.error("Credentials not found. Please check your secret setup.")
else:
    # Load the credentials from the secret
    credentials_dict = json.loads(credentials)

    # Save the credentials to the expected location
    os.makedirs(os.path.expanduser("~/.config/earthengine/"), exist_ok=True)
    with open(os.path.expanduser("~/.config/earthengine/credentials"), "w") as f:
        json.dump(credentials_dict, f)
        
ee.Initialize(project='ee-yashsacisro24')

# Define the Sentinel-2 ImageCollection
s2_collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')

# Function to add custom indices to the image
def add_indices(image):
    custom_ndvi = image.normalizedDifference(['B4', 'B3']).rename('Custom_NDVI')
    custom_ndwi = image.normalizedDifference(['B3', 'B2']).rename('Custom_NDWI')
    return image.addBands([custom_ndvi, custom_ndwi])

# Streamlit UI
st.title("Sentinel-2 NDVI and NDWI Analysis")

# User input for points
num_points = st.number_input("Enter the number of points:", min_value=1, value=1, step=1)
points = []

for i in range(num_points):
    lat = st.number_input(f"Enter latitude for point {i + 1}:", format="%.6f")
    lon = st.number_input(f"Enter longitude for point {i + 1}:", format="%.6f")
    name = st.text_input(f"Enter location name for point {i + 1}:")
    points.append((ee.Geometry.Point([lon, lat]), name))

# Date range input
start_date = st.date_input("Select start date:", datetime.now())
end_date = st.date_input("Select end date:", datetime.now())

# Date interval input
date_interval = st.number_input("Enter the date interval in days (e.g., 15):", min_value=1, value=15, step=1)

# Cloud percentage threshold input
cloud_threshold = st.number_input("Enter the maximum allowable CLOUDY_PIXEL_PERCENTAGE (e.g., 20):", min_value=0.0, value=20.0, step=0.1)

# Create a button to run the analysis
if st.button("Submit"):
    results = []
    current_date = start_date

    with st.spinner("Running analysis..."):
        while current_date <= end_date:
            next_date = current_date + timedelta(days=date_interval)

            # Convert to Earth Engine Date
            ee_current_date = ee.Date(current_date.strftime('%Y-%m-%d'))
            ee_next_date = ee.Date(next_date.strftime('%Y-%m-%d'))

            # Filter the ImageCollection for the current date range
            filtered_collection = s2_collection.filterDate(ee_current_date, ee_next_date) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_threshold))

            # Check if there are images available
            image_count = filtered_collection.size().getInfo()
            if image_count == 0:
                current_date += timedelta(days=date_interval)
                continue
            # Map the function to add custom indices
            custom_indices_collection = filtered_collection.map(add_indices)

            # Extract the values for the geometry points
            for point, name in points:
                values = custom_indices_collection.getRegion(point, 10).getInfo()

                # Extract values, ignoring None values
                valid_ndvi_values = [value[4] for value in values[1:] if value[4] is not None]
                valid_ndwi_values = [value[5] for value in values[1:] if value[5] is not None]

                # Calculate mean values for each location
                mean_ndvi = sum(valid_ndvi_values) / len(valid_ndvi_values) if valid_ndvi_values else None
                mean_ndwi = sum(valid_ndwi_values) / len(valid_ndwi_values) if valid_ndwi_values else None

                # Only append results if both NDVI and NDWI are not None
                if mean_ndvi is not None and mean_ndwi is not None:
                    results.append({
                        "Date": current_date.strftime('%Y-%m-%d'),  # Ensure date is a string
                        "Location": name,
                        "Custom_NDVI": mean_ndvi,
                        "Custom_ND VI": mean_ndwi,
                    })

            # Increment the date by the user-defined interval
            current_date += timedelta(days=date_interval)

    # Convert the results list to a DataFrame
    df = pd.DataFrame(results)

    # Display the results
    st.write(df)

    # Create a download button for the CSV file
    @st.cache_data
    def convert_df(df):
        return df.to_csv(index=False)

    csv = convert_df(df)

    st.download_button(
        label="Download data as CSV",
        data=csv,
        file_name='results.csv',
        mime='text/csv',
    )
