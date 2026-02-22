import os
import requests
import polyline
import xml.etree.ElementTree as ET

# Strava API credentials
STRAVA_ACCESS_TOKEN = "9273a3401810e2a52472a8c18983bc345264624e"
ACTIVITY_ID = "13492295062"  # Replace with actual activity ID

# Path to save the GPX file
SAVE_PATH = "/var/lib/docker/volumes/dawarich_dawarich_watched/_data/markus@photing.com"

# Function to get activity details from Strava
def get_activity_data(activity_id):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}, {response.text}")
        return None

    activity_data = response.json()
    print(activity_data)  # Print the full response for debugging
    return activity_data

# Function to convert activity data to GPX format
def generate_gpx(activity):
    poly = activity.get("map", {}).get("summary_polyline", "")
    if not poly:
        print("No GPS data found!")
        return None

    points = polyline.decode(poly)

    # Create GPX XML structure
    gpx = ET.Element("gpx", version="1.1", creator="StravaGPXExporter", xmlns="http://www.topografix.com/GPX/1/1")
    trk = ET.SubElement(gpx, "trk")
    name = ET.SubElement(trk, "name")
    name.text = activity["name"]
    trkseg = ET.SubElement(trk, "trkseg")

    for lat, lon in points:
        trkpt = ET.SubElement(trkseg, "trkpt", lat=str(lat), lon=str(lon))
        ET.SubElement(trkpt, "ele").text = "0"  # Elevation (set to 0 or fetch separately)

    # Convert to XML string
    return ET.tostring(gpx, encoding="utf-8").decode("utf-8")

# Main
activity = get_activity_data(ACTIVITY_ID)
gpx_data = generate_gpx(activity)

if gpx_data:
    # Ensure the save directory exists
    os.makedirs(SAVE_PATH, exist_ok=True)

    file_path = os.path.join(SAVE_PATH, f"{ACTIVITY_ID}.gpx")
    with open(file_path, "w") as file:
        file.write(gpx_data)

    print(f"GPX file saved as {file_path}")