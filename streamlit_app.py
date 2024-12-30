import streamlit as st
import geopandas as gpd
import pandas as pd
import osmnx as ox
import pydeck as pdk
import folium
from shapely.geometry import Point
import shapely.geometry as sg
from streamlit_folium import st_folium
import time

# --- PAGE SETUP ---
st.set_page_config(
    page_title="Walkability Map App",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Walkability Map App")
st.caption("Explore urban walkability with dynamic heatmaps.")


# --- SIDEBAR INTERFACE ---
st.sidebar.header("Location Selection")
location_method = st.sidebar.radio(
    "How would you like to select the location?",
    ["Text Input", "Map Click"],
    key="location_method_selector"
)

# Default Variables
Boundary = None
default_address = "San Francisco, CA"


# --- LOCATION SELECTION ---

# TEXT INPUT METHOD
if location_method == "Text Input":
    address = st.sidebar.text_input(
        "Enter a location:",
        value=default_address,
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

# MAP CLICK METHOD
else:
    st.sidebar.write("Click on the map to select a location.")

    # Default map location and zoom
    default_location = [37.7749, -122.4194]  # San Francisco, CA
    map_center = default_location

    # Create a Folium map
    m = folium.Map(location=map_center, zoom_start=12)

    # Add a clickable map
    folium.Marker(location=map_center, popup="Default Location").add_to(m)
    map_click = st_folium(
        m,
        width=700,
        height=500,
        key="map_click_selector"
    )

    # Extract clicked coordinates
    clicked_point = map_click.get("last_clicked")
    if clicked_point:
        lat = clicked_point["lat"]
        lon = clicked_point["lng"]
        st.sidebar.success(f"Coordinates selected: ({lat}, {lon})")
        
        try:
            with st.spinner("Finding the administrative boundary for your coordinates..."):
                # Fetch administrative boundaries
                point = (lat, lon)
                Perimeter = ox.features_from_point(
                    point, tags={"boundary": "administrative"}
                )
                if not Perimeter.empty:
                    # Merge multiple geometries if necessary
                    Boundary = Perimeter.geometry.unary_union
                    st.sidebar.success(f"Boundary found for clicked point: ({lat}, {lon})")
                else:
                    # Fallback: Create a buffer around the point
                    Boundary = sg.Point(lon, lat).buffer(0.01)  # ~1km radius
                    st.sidebar.warning(
                        "No administrative boundary found. Using a circular buffer (~1km) instead."
                    )
        except Exception as e:
            st.sidebar.warning("Failed to find an administrative boundary.")
            st.sidebar.write(f"Error: {e}")
            Boundary = sg.Point(lon, lat).buffer(0.01)  # Fallback buffer
    else:
        st.sidebar.info("Click on the map to select a location.")

# Ensure Boundary is defined
if Boundary is None:
    st.stop()

# Convert Boundary to WKT for caching compatibility
boundary_wkt = Boundary.wkt


# --- AMENITY CATEGORIES ---
st.sidebar.header("Amenity Filters")
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

# SPECIFIC AMENITY FILTER
st.sidebar.header("Specific Amenity Filter")
specific_amenity = st.sidebar.selectbox(
    "Choose a specific amenity:",
    options=["Transit Stations", "Libraries", "Restaurants"]
)


# --- FETCH DATA ---
from shapely import wkt  # Correct import for WKT

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



# Load selected categories
filtered_amenities = []
for category in selected_categories:
    tags = amenity_categories[category]
    amenities = fetch_amenities(boundary_wkt, tags)
    if not amenities.empty:
        amenities['category'] = category
        filtered_amenities.append(amenities)

# Add specific amenity filter
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

# --- MERGE AND VALIDATE AMENITY DATA ---

if filtered_amenities:
    # Combine all amenities data into one DataFrame
    all_amenities = pd.concat(filtered_amenities, ignore_index=True)
    all_amenities["x"] = all_amenities.geometry.centroid.x
    all_amenities["y"] = all_amenities.geometry.centroid.y
else:
    # Fallback to an empty DataFrame if no amenities are found
    st.warning("No amenities found for selected filters. Displaying an empty map.")
    all_amenities = pd.DataFrame(columns=["x", "y"])


# --- HEATMAP VISUALIZATION ---
st.header("Heatmap Visualization")

COLOR_SCALE = [
    [255, 255, 204],
    [161, 218, 180],
    [65, 182, 196],
    [44, 127, 184],
    [37, 52, 148]
]

chart_data = all_amenities[['x', 'y']]

Heatmap = pdk.Layer(
    "HeatmapLayer",
    data=chart_data,
    opacity=0.6,
    get_position='[x, y]',
    color_range=COLOR_SCALE,
    threshold=0.2,
)

view_state = pdk.ViewState(
    longitude=chart_data['x'].mean(),
    latitude=chart_data['y'].mean(),
    zoom=13
)

st.pydeck_chart(pdk.Deck(
    layers=[Heatmap],
    initial_view_state=view_state,
    tooltip={"text": "Heatmap of Selected Amenities"}
))

st.success("Visualization Complete! Explore your heatmap above.")
