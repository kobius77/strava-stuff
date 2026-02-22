import os
import sys
import re
import requests
import datetime
import pytz

# Strava API credentials
STRAVA_ACCESS_TOKEN = "b05855610077c27761d5bc12534461e2c1a6ec5b"
STRAVA_REFRESH_TOKEN = "54f758c454a365c3590cef1455f2e810b915b367"
CLIENT_ID = "15296"
CLIENT_SECRET = "9ea4462f4dcb2078740d39ff7f055b1f29726139"

# Audiobookshelf API credentials and server URL
ABS_API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiIwZmYyZmNhMi02MjQ2LTQxYjQtOGFiMi1hMGRiMGJkZTk4NGQiLCJ1c2VybmFtZSI6Im1hcmt1cyIsImlhdCI6MTcyNjM0NjAzMn0.GGirW-2b7YBUFBlDzUjV9VgwoUvt-NkQgU6oIQcVR7k"
ABS_URL = "https://abs.oida.top"

# -------------------------
# Strava helper functions
# -------------------------
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
        print("Strava token refreshed successfully!")
    else:
        print(f"Error refreshing token: {response.status_code}, {response.text}")

def get_last_activity():
    """Retrieve the most recent Strava activity (within the past 24 hours)."""
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    local_tz = pytz.timezone("Europe/Vienna")
    twenty_four_hours_ago = datetime.datetime.now(local_tz) - datetime.timedelta(hours=24)
    twenty_four_hours_ago_utc = twenty_four_hours_ago.astimezone(pytz.utc).timestamp()
    params = {"after": twenty_four_hours_ago_utc, "per_page": 1}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 401:
        print("Strava token expired! Refreshing...")
        refresh_access_token()
        headers["Authorization"] = f"Bearer {STRAVA_ACCESS_TOKEN}"
        response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print("Error getting recent activities:", response.status_code, response.text)
        return None
    activities = response.json()
    if not activities:
        print("No recent activities found.")
        return None
    return activities[0]

def update_activity(activity_id, new_title, new_description):
    """Update the activity's name and description on Strava."""
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    payload = {"name": new_title, "description": new_description}
    response = requests.put(url, headers=headers, data=payload)
    if response.status_code == 200:
        print(f"Activity {activity_id} updated successfully.")
        return True
    else:
        print("Error updating activity:", response.status_code, response.text)
        return False

def print_strava_activity_debug(activity):
    """Print Strava activity details for debugging."""
    activity_id = activity.get("id", "N/A")
    start_date = activity.get("start_date", "Unknown")
    try:
        start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
    except Exception:
        start_dt = None
    elapsed = activity.get("elapsed_time", 0)
    if start_dt:
        end_dt = start_dt + datetime.timedelta(seconds=elapsed)
        print("Strava Activity Details:")
        print(f"  ID: {activity_id}")
        print(f"  Start (UTC): {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Elapsed time: {elapsed} seconds")
        print(f"  End (UTC):   {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("Strava Activity Details: Unable to parse start_date.")

# -------------------------
# Audiobookshelf helper functions
# -------------------------
def get_abs_session_during_activity(activity):
    """
    Query ABS endpoint /api/me/listening-sessions and check for a session whose
    time window overlaps with the Strava activity's timeframe.
    
    ABS timestamps are in milliseconds in ABS's local time (assumed "Europe/Vienna").
    """
    url = f"{ABS_URL}/api/me/listening-sessions"
    headers = {"Authorization": f"Bearer {ABS_API_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error fetching ABS sessions:", response.status_code, response.text)
        return None
    data = response.json()
    sessions = data.get("sessions", [])
    if not sessions:
        return None

    # Correctly parse the activity's start time as UTC.
    activity_start = datetime.datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).timestamp()
    activity_end = activity_start + activity.get("elapsed_time", 0)

    abs_tz = pytz.timezone("Europe/Vienna")
    
    for session in sessions:
        session_start_dt = datetime.datetime.fromtimestamp(session.get("startedAt", 0) / 1000.0, tz=abs_tz)
        session_start_utc = session_start_dt.astimezone(pytz.utc).timestamp()
        session_end_ms = session.get("updatedAt", session.get("startedAt", 0))
        session_end_dt = datetime.datetime.fromtimestamp(session_end_ms / 1000.0, tz=abs_tz)
        session_end_utc = session_end_dt.astimezone(pytz.utc).timestamp()
        
        # Check for overlap: session ends after activity starts AND session starts before activity ends.
        if session_end_utc >= activity_start and session_start_utc <= activity_end:
            return session
    return None

def print_last_three_sessions():
    """
    For debugging, query ABS endpoint /api/me/listening-sessions and output the last 3 listening sessions
    with both ABS local times and converted UTC times.
    """
    url = f"{ABS_URL}/api/me/listening-sessions"
    headers = {"Authorization": f"Bearer {ABS_API_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Error fetching ABS sessions:", response.status_code, response.text)
        return
    data = response.json()
    sessions = data.get("sessions", [])
    if not sessions:
        print("No listening sessions found.")
        return
    sessions = sorted(sessions, key=lambda s: s.get("startedAt", 0), reverse=True)
    abs_tz = pytz.timezone("Europe/Vienna")
    print("Last 3 listening sessions:")
    for session in sessions[:3]:
        start_dt = datetime.datetime.fromtimestamp(session.get("startedAt", 0) / 1000.0, tz=abs_tz)
        start_dt_utc = start_dt.astimezone(pytz.utc)
        end_ms = session.get("updatedAt", session.get("startedAt", 0))
        end_dt = datetime.datetime.fromtimestamp(end_ms / 1000.0, tz=abs_tz)
        end_dt_utc = end_dt.astimezone(pytz.utc)
        print(f"Session ID: {session.get('id', 'N/A')}")
        print(f"  Start (ABS local): {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Start (UTC):       {start_dt_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  End (ABS local):   {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  End (UTC):         {end_dt_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        print("----------")

# -------------------------
# Main function
# -------------------------
def main():
    # If '--debug-sessions' is provided, output debugging info and exit.
    if len(sys.argv) > 1 and sys.argv[1] == "--debug-sessions":
        print("Debugging ABS Sessions:")
        print_last_three_sessions()
        print("\nDebugging Last Strava Activity:")
        last_activity = get_last_activity()
        if last_activity:
            print_strava_activity_debug(last_activity)
        return

    # Retrieve the last Strava activity
    last_activity = get_last_activity()
    if not last_activity:
        print("No activity found to update.")
        return

    activity_id = last_activity["id"]
    start_timestamp = last_activity.get("start_date", "Unknown")
    print(f"Last activity ID: {activity_id} started at {start_timestamp}")

    # Query ABS for a listening session that overlaps with this activity
    abs_session = get_abs_session_during_activity(last_activity)
    if abs_session is None:
        print("No ABS listening session found during the activity.")
        return

    # Extract media details from the session
    media_metadata = abs_session.get("mediaMetadata", {})
    media_title = media_metadata.get("title", "Unknown Title")
    media_type = abs_session.get("mediaType", "Media")

    # Update the activity's description: append media info
    current_description = last_activity.get("description", "")
    if current_description:
        new_description = current_description + "\n"
    else:
        new_description = ""
    new_description += f"Listening to {media_type}: {media_title}"

    # Update the activity's title: append " 🎧📖" if not already present
    current_title = last_activity.get("name", "")
    if "🎧📖" not in current_title:
        new_title = current_title + " 🎧📖"
    else:
        new_title = current_title

    # Update the activity on Strava with the new title and description
    update_activity(activity_id, new_title, new_description)

if __name__ == "__main__":
    main()