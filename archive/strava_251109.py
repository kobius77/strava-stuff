import os
import requests
import polyline
import xml.etree.ElementTree as ET
import datetime
import math
import json
import pytz
import regex as re
import sys

# Strava API credentials
STRAVA_ACCESS_TOKEN = "b05855610077c27761d5bc12534461e2c1a6ec5b"
STRAVA_REFRESH_TOKEN = "54f758c454a365c3590cef1455f2e810b915b367"
CLIENT_ID = "15296"
CLIENT_SECRET = "9ea4462f4dcb2078740d39ff7f055b1f29726139"

# Path to save the GPX file
SAVE_PATH = "/var/lib/docker/volumes/dawarich_dawarich_watched/_data/markus@photing.com"

##
## prior lines containing config variables omitted
##

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

# Function to update an activity's name on Strava via the API
def update_activity_name(activity_id, new_name):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    payload = {"name": new_name}
    response = requests.put(url, headers=headers, data=payload)
    if response.status_code == 200:
        print(f"Activity {activity_id} renamed to: {new_name}")
        return True
    else:
        print(f"Error updating activity {activity_id}: {response.status_code}, {response.text}")
        return False

# Function to get recent activities (last 12 hours)
def get_recent_activities():
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    local_tz = pytz.timezone("Europe/Vienna")  # Default timezone (adjust if needed)
    one_hour_ago = datetime.datetime.now(local_tz) - datetime.timedelta(hours=12)
    one_hour_ago_utc = one_hour_ago.astimezone(pytz.utc).timestamp()

    params = {"after": one_hour_ago_utc}
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 401:
        print("Access token expired! Refreshing...")
        refresh_access_token()
        headers["Authorization"] = f"Bearer {STRAVA_ACCESS_TOKEN}"
        response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}, {response.text}")
        return []
    
    return response.json()

# Function to get activity details
def get_activity_data(activity_id):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 401:
        print("Access token expired! Refreshing...")
        refresh_access_token()
        headers["Authorization"] = f"Bearer {STRAVA_ACCESS_TOKEN}"
        response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}, {response.text}")
        return None
    
    return response.json()

# Function to query previous day's runs and get the maximum counter
def get_previous_day_counter(activity):
    # Parse the activity's start time and convert to local time using its timezone
    start_time = datetime.datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ")
    timezone_str = activity.get("timezone", "UTC")
    timezone_parts = timezone_str.split(" ")
    if len(timezone_parts) > 1:
        timezone_name = timezone_parts[-1]  # e.g. "Europe/Vienna"
    else:
        timezone_name = "UTC"
    tz = pytz.timezone(timezone_name)
    local_start = start_time.replace(tzinfo=pytz.utc).astimezone(tz)
    current_date = local_start.date()
    previous_date = current_date - datetime.timedelta(days=1)

    # Create timestamps for the previous day in local time then convert to UTC
    day_start_local = datetime.datetime.combine(previous_date, datetime.time.min)
    day_end_local = datetime.datetime.combine(previous_date, datetime.time.max)
    day_start_utc = tz.localize(day_start_local).astimezone(pytz.utc).timestamp()
    day_end_utc = tz.localize(day_end_local).astimezone(pytz.utc).timestamp()

    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    params = {"after": day_start_utc, "before": day_end_utc}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"Error fetching previous day's activities: {response.status_code}, {response.text}")
        return None
    activities = response.json()
    
    # Look for runs that have a counter in the name (format "#NNN")
    max_counter = None
    pattern = re.compile(r"#(\d{1,3})")
    for act in activities:
        if act.get("type", "").lower() == "run":
            m = pattern.search(act.get("name", ""))
            if m:
                counter = int(m.group(1))
                if max_counter is None or counter > max_counter:
                    max_counter = counter
    if max_counter is not None:
        return max_counter + 1
    return None

# Function to convert activity data to GPX format (timestamps remain in UTC)
def generate_gpx(activity):
    poly = activity.get("map", {}).get("summary_polyline", "")
    if not poly:
        print("No GPS data found!")
        return None

    points = polyline.decode(poly)
    # Parse the start time (this remains in UTC)
    start_time = datetime.datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ")
    
    gpx = ET.Element("gpx", version="1.1", creator="StravaGPXExporter", xmlns="http://www.topografix.com/GPX/1/1")
    trk = ET.SubElement(gpx, "trk")
    name = ET.SubElement(trk, "name")
    # Use the original activity name for the GPX file
    name.text = activity.get("name", "")
    trkseg = ET.SubElement(trk, "trkseg")
    
    for i, (lat, lon) in enumerate(points):
        timestamp = start_time + datetime.timedelta(seconds=i * (activity["elapsed_time"] / len(points)))
        timestamp_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        trkpt = ET.SubElement(trkseg, "trkpt", lat=str(lat), lon=str(lon))
        ET.SubElement(trkpt, "ele").text = "0"
        ET.SubElement(trkpt, "time").text = timestamp_str
    
    return ET.tostring(gpx, encoding="utf-8").decode("utf-8")

# Main
if len(sys.argv) > 1:
    # A specific activity ID was provided as a command-line parameter
    activity_id = sys.argv[1]
    activity_data = get_activity_data(activity_id)
    if activity_data is None:
        print(f"Could not fetch data for activity {activity_id}")
        sys.exit(1)
    
    # For a run, check if its name doesn't already have a counter.
    if activity_data.get("type", "").lower() == "run":
        if not re.search(r"#\d{1,3}", activity_data.get("name", "")):
            new_counter = get_previous_day_counter(activity_data)
            if new_counter is not None:
                # Format with leading zeros (3 digits)
                counter_str = f"#{new_counter:03d}"
                new_name = f"{counter_str} {activity_data['name']}"
                # Update the activity name on Strava via the API
                if update_activity_name(activity_id, new_name):
                    # If update is successful, update the local copy used for GPX generation if desired
                    activity_data["name"] = new_name
    
    gpx_data = generate_gpx(activity_data)
    if gpx_data:
        os.makedirs(SAVE_PATH, exist_ok=True)
        file_path = os.path.join(SAVE_PATH, f"{activity_id}.gpx")
        with open(file_path, "w") as file:
            file.write(gpx_data)
        print(f"GPX file saved as {file_path}")
else:
    # Process recent activities (as defined in get_recent_activities)
    recent_activities = get_recent_activities()
    
    for activity in recent_activities:
        activity_id = activity["id"]
        activity_data = get_activity_data(activity_id)
        if not activity_data:
            continue
    
        # Check if the activity is a run and if its name doesn't already have a counter.
        original_name = activity_data.get("name", "")
        if activity_data.get("type", "").lower() == "run":
            if not re.search(r"#\d{1,3}", original_name):
                new_counter = get_previous_day_counter(activity_data)
                if new_counter is not None:
                    # Format with leading zeros (3 digits)
                    counter_str = f"#{new_counter:03d}"
                    new_name = f"{counter_str} {original_name}"
                    if update_activity_name(activity_id, new_name):
                        # Update the local copy with the new name if update succeeded
                        activity_data["name"] = new_name
    
        gpx_data = generate_gpx(activity_data)
    
        if gpx_data:
            os.makedirs(SAVE_PATH, exist_ok=True)
            file_path = os.path.join(SAVE_PATH, f"{activity_id}.gpx")
            with open(file_path, "w") as file:
                file.write(gpx_data)
            print(f"GPX file saved as {file_path}")