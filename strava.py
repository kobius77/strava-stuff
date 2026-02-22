import os
import requests
import polyline
import xml.etree.ElementTree as ET
import datetime
import math
import json
import pytz
import re
import sys
import sqlite3
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
STRAVA_ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")

# Segment IDs for the "Iron Chain" Streak (Cycling)
BIG_SEGMENT_ID = 10792500  
SMALL_SEGMENT_ID = 2517149 

# Path to save the GPX file
SAVE_PATH = "/var/lib/docker/volumes/dawarich_dawarich_watched/_data/markus@photing.com"

# --- HELPER FUNCTIONS ---

def refresh_access_token():
    global STRAVA_ACCESS_TOKEN, STRAVA_REFRESH_TOKEN 
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
        STRAVA_REFRESH_TOKEN = data["refresh_token"] 
        print("Token refreshed successfully!")
    else:
        print(f"Error refreshing token: {response.status_code}, {response.text}")

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

def get_recent_activities():
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    local_tz = pytz.timezone("Europe/Vienna") 
    one_hour_ago = datetime.datetime.now(local_tz) - datetime.timedelta(hours=14)
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

def get_activity_data(activity_id):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 401:
        refresh_access_token()
        headers["Authorization"] = f"Bearer {STRAVA_ACCESS_TOKEN}"
        response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    return response.json()

# --- LOGIC ENGINE 1: RUNNING / NORDIC SKI (Daily Streak) ---
def calculate_run_streak(current_activity):
    print("--- Executing RUN/SKI Logic ---")
    
    # 1. Get current date (Local)
    start_time = datetime.datetime.strptime(current_activity["start_date"], "%Y-%m-%dT%H:%M:%SZ")
    timezone_str = current_activity.get("timezone", "UTC")
    timezone_name = timezone_str.split(" ")[-1] if len(timezone_str.split(" ")) > 1 else "UTC"
    tz = pytz.timezone(timezone_name)
    current_activity_date = start_time.replace(tzinfo=pytz.utc).astimezone(tz).date()

    # 2. Fetch History (Look deeper to ignore Bike rides)
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    params = {"per_page": 100} # Increased to 100 to see past bike rides
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200: return None
    activities = response.json()

    # 3. Find Last Run
    pattern = re.compile(r"#(\d+)")
    for act in activities:
        if str(act["id"]) == str(current_activity["id"]): continue
        
        # STRICT FILTER: Only look at runs/skis
        if act.get("type", "").lower() not in {"run", "nordicski"}: continue

        match = pattern.search(act.get("name", ""))
        if match:
            last_counter = int(match.group(1))
            act_time = datetime.datetime.strptime(act["start_date"], "%Y-%m-%dT%H:%M:%SZ")
            act_local_date = act_time.replace(tzinfo=pytz.utc).astimezone(tz).date()
            days_diff = (current_activity_date - act_local_date).days

            if days_diff == 1:
                return last_counter + 1
            elif days_diff == 0:
                print("Already ran today.")
                return None
            else:
                print(f"Streak broken! Last run was {days_diff} days ago.")
                return None 
    return None

# --- LOGIC ENGINE 2: CYCLING (Weekly Segment Streak) ---
def calculate_cycle_streak(current_activity):
    print("--- Executing CYCLING Logic ---")

    # 1. Check Segments in Current Ride
    efforts = current_activity.get('segment_efforts', [])
    current_seg_ids = [e['segment']['id'] for e in efforts]
    big_loops = current_seg_ids.count(BIG_SEGMENT_ID)
    small_loops = current_seg_ids.count(SMALL_SEGMENT_ID)

    if big_loops == 0 and small_loops == 0:
        print("No streak segments found in this ride.")
        return None

    # 2. Fetch History
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    params = {"per_page": 100} 
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200: return None
    activities = response.json()

    pattern = re.compile(r"#(\d+)")
    last_streak_ride_summary = None
    last_count = 0

    for act in activities:
        if str(act["id"]) == str(current_activity["id"]): continue
        
        # STRICT FILTER: Only look at Rides
        if act.get("type", "").lower() != "ride": continue

        match = pattern.search(act.get("name", ""))
        if match:
            last_streak_ride_summary = act
            last_count = int(match.group(1))
            break 

    if not last_streak_ride_summary:
        print("No previous cycling streak found.")
        return None 

    # 3. Calculate Debt
    def get_monday(dt_str):
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.date() - datetime.timedelta(days=dt.weekday())

    curr_monday = get_monday(current_activity["start_date"])
    last_monday = get_monday(last_streak_ride_summary["start_date"])
    weeks_diff = (curr_monday - last_monday).days // 7
    weeks_missed = max(0, weeks_diff - 1)

    if weeks_diff == 0:
        print("Already counted a ride this week.")
        return None

    # 4. Check Requirements
    req_big = weeks_missed + 1
    req_small = weeks_missed + 2
    is_success = False

    if big_loops >= req_big:
        is_success = True
    elif small_loops >= req_small:
        is_success = True
    elif weeks_missed == 0 and small_loops == 1 and big_loops == 0:
        # Weak Link Check
        last_streak_details = get_activity_data(last_streak_ride_summary["id"])
        if last_streak_details:
            prev_ids = [e['segment']['id'] for e in last_streak_details.get('segment_efforts', [])]
            if prev_ids.count(BIG_SEGMENT_ID) >= 1 or prev_ids.count(SMALL_SEGMENT_ID) >= 2:
                is_success = True

    if is_success:
        return last_count + weeks_missed + 1
    return None

# --- GPX GENERATOR (Shared) ---
def generate_gpx(activity):
    poly = activity.get("map", {}).get("summary_polyline", "")
    if not poly: return None
    points = polyline.decode(poly)
    start_time = datetime.datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ")
    
    gpx = ET.Element("gpx", version="1.1", creator="StravaGPXExporter", xmlns="http://www.topografix.com/GPX/1/1")
    trk = ET.SubElement(gpx, "trk")
    ET.SubElement(trk, "name").text = activity.get("name", "")
    trkseg = ET.SubElement(trk, "trkseg")
    
    for i, (lat, lon) in enumerate(points):
        timestamp = start_time + datetime.timedelta(seconds=i * (activity["elapsed_time"] / len(points)))
        trkpt = ET.SubElement(trkseg, "trkpt", lat=str(lat), lon=str(lon))
        ET.SubElement(trkpt, "time").text = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return ET.tostring(gpx, encoding="utf-8").decode("utf-8")

# --- SEGMENT MONITORING ---
def init_segment_db():
    conn = sqlite3.connect("segment_history.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS segment_efforts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            segment_id INTEGER NOT NULL,
            effort_count INTEGER NOT NULL,
            athlete_count INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def get_segment_data(segment_id):
    url = f"https://www.strava.com/api/v3/segments/{segment_id}"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 401:
        refresh_access_token()
        headers["Authorization"] = f"Bearer {STRAVA_ACCESS_TOKEN}"
        response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error fetching segment {segment_id}: {response.status_code}, {response.text}")
        return None
    return response.json()

def record_segment_efforts(segment_id):
    data = get_segment_data(segment_id)
    if not data:
        return
    
    effort_count = data.get("effort_count")
    athlete_count = data.get("athlete_count")
    
    conn = init_segment_db()
    
    last_effort = conn.execute(
        "SELECT effort_count FROM segment_efforts WHERE segment_id = ? ORDER BY timestamp DESC LIMIT 1",
        (segment_id,)
    ).fetchone()
    
    diff = None
    if last_effort:
        diff = effort_count - last_effort[0]
        print(f"Effort difference: {diff}")
    
    conn.execute(
        "INSERT INTO segment_efforts (segment_id, effort_count, athlete_count) VALUES (?, ?, ?)",
        (segment_id, effort_count, athlete_count)
    )
    conn.commit()
    print(f"Recorded segment {segment_id}: {effort_count} efforts, {athlete_count} athletes")
    conn.close()
    
    if diff is not None and diff >= 0:
        send_to_webhook(diff, segment_id)

def send_to_webhook(diff, segment_id):
    webhook_url = "https://n8.oida.top/webhook-test/45b02c6b-986a-42f6-adb5-135e69f8e121"
    payload = {
        "effort_diff": diff,
        "segment_id": segment_id
    }
    try:
        response = requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"})
        if response.status_code in (200, 201, 202):
            print(f"Sent {diff} to webhook")
        else:
            print(f"Webhook error: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Webhook request failed: {e}")

# --- MAIN EXECUTION BLOCK ---
def process_activity(activity_id):
    activity_data = get_activity_data(activity_id)
    if not activity_data: 
        print(f"Could not fetch {activity_id}")
        return

    original_name = activity_data.get("name", "")
    activity_type = activity_data.get("type", "").lower()
    
    # Check if we have already renamed this specific activity
    if re.search(r"#\d{1,3}", original_name):
        print(f"Activity {activity_id} already has a streak counter.")
    else:
        new_counter = None
        
        # === ROUTING LOGIC ===
        if activity_type in {"run", "nordicski"}:
            new_counter = calculate_run_streak(activity_data)
        elif activity_type == "ride":
            new_counter = calculate_cycle_streak(activity_data)
        
        # Apply Rename
        if new_counter is not None:
            counter_str = f"#{new_counter:03d}"
            new_name = f"{counter_str} {original_name}"
            if update_activity_name(activity_id, new_name):
                activity_data["name"] = new_name

    # Generate GPX (For all types)
    gpx_data = generate_gpx(activity_data)
    if gpx_data:
        os.makedirs(SAVE_PATH, exist_ok=True)
        file_path = os.path.join(SAVE_PATH, f"{activity_id}.gpx")
        with open(file_path, "w") as file:
            file.write(gpx_data)
        print(f"GPX file saved as {file_path}")

# Script Entry Point
if len(sys.argv) > 1:
    if sys.argv[1] == "--segment":
        segment_id = int(sys.argv[2]) if len(sys.argv) > 2 else BIG_SEGMENT_ID
        record_segment_efforts(segment_id)
    else:
        process_activity(sys.argv[1])
else:
    recent_activities = get_recent_activities()
    for activity in recent_activities:
        process_activity(activity["id"])