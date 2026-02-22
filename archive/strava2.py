import os
import requests
import polyline
import xml.etree.ElementTree as ET
import datetime
import math
import json
import pytz

# Strava API credentials
STRAVA_ACCESS_TOKEN = "9273a3401810e2a52472a8c18983bc345264624e"
STRAVA_REFRESH_TOKEN = "468fec2ac8f87dab7fe4136f7e69efdf5a0c661c"
CLIENT_ID = "15296"
CLIENT_SECRET = "c3ace7dd2d22c6361659612ce8fa4dfc214607d5"
ACTIVITY_ID = "13458618188"  # Replace with actual activity ID

# Path to save the GPX file
SAVE_PATH = "/var/lib/docker/volumes/dawarich_dawarich_watched/_data/markus@photing.com"

# Function to refresh the access token
def refresh_access_token():
    global STRAVA_ACCESS_TOKEN, STRAVA_REFRESH_TOKEN  # Declare globals at the beginning
	
    url = "https://www.strava.com/api/v3/oauth/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": STRAVA_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        data = response.json()
        STRAVA_ACCESS_TOKEN = data["access_token"]
        STRAVA_REFRESH_TOKEN = data["refresh_token"]  # Store new refresh token

        print("Token refreshed successfully!")
    else:
        print(f"Error refreshing token: {response.status_code}, {response.text}")


# Function to get activity details from Strava
def get_activity_data(activity_id):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}

    response = requests.get(url, headers=headers)

    if response.status_code == 401:  # Unauthorized → Token expired
        print("Access token expired! Refreshing...")
        refresh_access_token()
        headers["Authorization"] = f"Bearer {STRAVA_ACCESS_TOKEN}"
        response = requests.get(url, headers=headers)  # Retry request with new token

    if response.status_code != 200:
        print(f"Error: {response.status_code}, {response.text}")
        return None

    return response.json()

# Function to convert activity data to GPX format
def generate_gpx(activity):
    poly = activity.get("map", {}).get("summary_polyline", "")
    if not poly:
        print("No GPS data found!")
        return None

    points = polyline.decode(poly)
    start_time = datetime.datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ")
    
    # Convert to activity's timezone
    timezone_str = activity.get("timezone", "UTC")
    timezone_parts = timezone_str.split(" ")
    if len(timezone_parts) > 1:
        timezone_name = timezone_parts[-1]  # Get the last part, which is the actual timezone name
    else:
        timezone_name = "UTC"

    timezone = pytz.timezone(timezone_name)  # Convert to correct timezone

    start_time = start_time.replace(tzinfo=pytz.utc).astimezone(timezone)
    
    gpx = ET.Element("gpx", version="1.1", creator="StravaGPXExporter", xmlns="http://www.topografix.com/GPX/1/1")
    trk = ET.SubElement(gpx, "trk")
    name = ET.SubElement(trk, "name")
    name.text = activity["name"]
    trkseg = ET.SubElement(trk, "trkseg")
    
    for i, (lat, lon) in enumerate(points):
        timestamp = start_time + datetime.timedelta(seconds=i * (activity["elapsed_time"] / len(points)))
        timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        trkpt = ET.SubElement(trkseg, "trkpt", lat=str(lat), lon=str(lon))
        ET.SubElement(trkpt, "ele").text = "0"
        ET.SubElement(trkpt, "time").text = timestamp_str
    
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