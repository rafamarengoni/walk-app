import streamlit as st
import geopandas as gpd
import pandas as pd
import osmnx as ox
import folium
from streamlit_folium import st_folium
from shapely import wkt
from shapely.geometry import Point
import shapely.geometry as sg
import time
from folium.plugins import HeatMap

# --- PAGE SETUP ---
st.set_page_config(
    page_title="Walkability Map App",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Walkability Map App")
st.caption("Explore urban walkability with dynamic heatmaps and interactive maps.")


# --- SIDEBAR INTERFACE ---
st.sidebar.header("Location and Filter Settings")

# --- LOCATION INPUT ---
st.sidebar.subheader("Select a Location")
location_method = st.sidebar.radio(
    "Choose how to set the location:",
    ["Text Input", "Map Click"],
    key="location_method_selector"
)

# Default location for the map
default_location = [37.7749, -122.4194]  # San Francisco, CA
Boundary = None


# --- LOCATION SELECTION ---
if location_method == "Text Input":
    address = st.sidebar.text_input(
        "Enter a location:",
        value="San Francisco, CA",
        help="Enter a city, neighborhood, or address.",
        key="location_text_input"
    )
    try:
        with st.spinner("Geocoding your address..."):
            Perimeter = ox.geocode_to_gdf(address)
            Boundary = Perimeter['geometry'].iloc[0]
            st.sidebar.success(f"Location found: {address}")
    except Exception as e:
        st.sidebar.warning("Failed to geocode the address. Try refining your input.")
        st.sidebar.write(f"Error: {e}")
        Boundary = sg.Point(default_location[1], default_location[0]).buffer(0.01)

else:
    st.sidebar.write("Click on the map to set a location.")


# --- AMENITY FILTERS ---
st.sidebar.subheader("Amenity Filters")
amenity_categories = {
    "Entertainment": {"amenity": ["arts_centre", "cinema", "nightclub", "theatre"]},
    "Civic": {"amenity": ["courthouse", "fire_station", "post_office"]},
    "Historic": {"historic": True},
    "Tourism": {"tourism": True},
    "FB (Food & Beverage)": {"amenity": ["cafe", "restaurant", "pub"]}
}

selected_categories = st.sidebar.multiselect(
    "Select amenity categories:",
    options=list(amenity_categories.keys()),
    default=["FB (Food & Beverage)"]
)

# Specific amenity selection
st.sidebar.subheader("Specific Amenity Filter")
specific_amenity = st.sidebar.selectbox(
    "Choose a specific amenity:",
    options=["Transit Stations", "Libraries", "Restaurants"]
)


# --- FETCH AMENITY DATA ---
@st.cache_data
def fetch_amenities(boundary_wkt: str, tags: dict):
    """
    Fetch amenities using OSMnx from a boundary represented as a WKT string.
    """
    try:
        boundary = wkt.loads(boundary_wkt)  # Deserialize WKT back to geometry
        return ox.features_from_polygon(boundary, tags)
    except Exception as e:
        st.sidebar.warning(f"Failed to fetch amenities: {e}")
        return gpd.GeoDataFrame()


# Prepare map data
filtered_amenities = []
if Boundary is not None:
    boundary_wkt = Boundary.wkt
    
    # Fetch amenities from categories
    for category in selected_categories:
        tags = amenity_categories[category]
        amenities = fetch_amenities(boundary_wkt, tags)
        if not amenities.empty:
            amenities['category'] = category
            filtered_amenities.append(amenities)

    # Fetch specific amenities
    if specific_amenity == "Transit Stations":
        tags = {"amenity": "bus_station"}
    elif specific_amenity == "Libraries":
        tags = {"amenity": "library"}
    elif specific_amenity == "Restaurants":
        tags = {"amenity": "restaurant"}
    
    specific_data = fetch_amenities(boundary_wkt, tags)
    if not specific_data.empty:
        specific_data['category'] = specific_amenity
        filtered_amenities.append(specific_data)

    # Merge all amenities
    if filtered_amenities:
        all_amenities = pd.concat(filtered_amenities, ignore_index=True)
        all_amenities["x"] = all_amenities.geometry.centroid.x
        all_amenities["y"] = all_amenities.geometry.centroid.y
    else:
        all_amenities = pd.DataFrame(columns=["x", "y"])

# --- INTERACTIVE MAP WITH HEATMAP ---
st.subheader("Interactive Map with Heatmap and Clickable Selection")

# Create the base map
m = folium.Map(location=default_location, zoom_start=13)

# Add heatmap layer if data exists
if not all_amenities.empty:
    HeatMap(min_opacity=0.1,
        data=all_amenities[['y', 'x']].values.tolist(),
        radius=15,
        blur=5,
        max_zoom=1,
    ).add_to(m)

# Capture map clicks
map_click = st_folium(
    m,
    width=800,
    height=600,
    key="folium_map_click"
)

# Handle map click
clicked_point = map_click.get("last_clicked")
if clicked_point:
    lat = clicked_point["lat"]
    lon = clicked_point["lng"]
    st.sidebar.success(f"Clicked Coordinates: ({lat}, {lon})")
    Boundary = sg.Point(lon, lat).buffer(0.01)  # Fallback circular buffer

    folium.Marker(
        location=[lat, lon],
        popup="Selected Point",
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)

# Display the map
st_folium(m, width=800, height=600, key="main_map_display")

st.success("Interactive Map Ready! Click on the map or adjust filters to explore.")
