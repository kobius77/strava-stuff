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

def main():
    activity = get_last_activity()
    if activity:
        print_strava_activity_debug(activity)
    else:
        print("No activity to display.")

if __name__ == "__main__":
    main()