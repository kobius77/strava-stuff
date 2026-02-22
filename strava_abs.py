import os
import sys
import re
import requests
import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()

# Strava API credentials
STRAVA_ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")

# Audiobookshelf API credentials and server URL
ABS_API_TOKEN = os.getenv("ABS_API_TOKEN")
ABS_URL = os.getenv("ABS_URL")

# Last.fm credentials
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_USER = os.getenv("LASTFM_USER")
LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"

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
    
    # Increase per_page to ensure we get all activities in the window
    params = {"after": twenty_four_hours_ago_utc, "per_page": 30}
    
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
    
    # 'after' param returns chronological order (Oldest -> Newest).
    # We want the LAST item in the list to get the most recent activity.
    return activities[-1]

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
        
        # Check for overlap
        if session_end_utc >= activity_start and session_start_utc <= activity_end:
            return session
    return None

def print_last_three_sessions():
    """Debug helper for ABS sessions."""
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
# Last.fm helper functions
# -------------------------
def get_lastfm_tracks_for_window(start_time, end_time):
    """Fetches all scrobbled tracks from Last.fm within a given time window."""
    from_timestamp = int(start_time.timestamp())
    to_timestamp = int(end_time.timestamp())

    payload = {
        "method": "user.getRecentTracks",
        "user": LASTFM_USER,
        "api_key": LASTFM_API_KEY,
        "from": from_timestamp,
        "to": to_timestamp,
        "format": "json",
        "limit": 200 
    }
    
    try:
        response = requests.get(LASTFM_API_URL, params=payload)
        response.raise_for_status() 
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Last.fm: {e}")
        return None

    data = response.json()
    
    if "recenttracks" not in data or "track" not in data["recenttracks"]:
        print("Last.fm response OK, but no 'recenttracks' key found.")
        return None

    tracks = data["recenttracks"]["track"]
    
    if not tracks:
        print("No tracks scrobbled in this time window.")
        return None

    if not isinstance(tracks, list):
        tracks = [tracks]

    formatted_tracks = []
    for track in reversed(tracks):
        if "@attr" in track and track["@attr"].get("nowplaying") == "true":
            continue
        artist = track.get("artist", {}).get("#text", "Unknown Artist")
        name = track.get("name", "Unknown Track")
        formatted_tracks.append(f"{artist} - {name}")
        
    unique_tracks = []
    seen = set()
    for item in formatted_tracks:
        if item not in seen:
            unique_tracks.append(item)
            seen.add(item)

    return unique_tracks

# -------------------------
# Main function
# -------------------------
def main():
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
    current_title = last_activity.get("name", "")
    current_description = last_activity.get("description", "")
    print(f"Found activity: {current_title} ({activity_id})")

    # --- Check for Audiobookshelf (ABS) session first ---
    abs_session = get_abs_session_during_activity(last_activity)
    
    if abs_session:
        print("Found overlapping ABS session.")
        media_metadata = abs_session.get("mediaMetadata", {})
        media_title = media_metadata.get("title", "Unknown Title")
        media_type = abs_session.get("mediaType", "Media")
        
        # Get author(s) - FIX APPLIED HERE
        authors = media_metadata.get("authors", [])
        author_names = []
        
        if isinstance(authors, list):
            for author in authors:
                # If author is a dictionary, extract "name"
                if isinstance(author, dict):
                    author_names.append(author.get("name", ""))
                # If author is already a string, use it directly
                else:
                    author_names.append(str(author))
            
            # Filter out empty names and join
            author_str = ", ".join(filter(None, author_names))
        else:
            author_str = str(authors)
            
        # Update the activity's description
        if current_description:
            new_description = current_description + "\n"
        else:
            new_description = ""
            
        # Add Title and [by: Author]
        new_description += f"Listening to {media_type}: {media_title}"
        if author_str:
            new_description += f" [by: {author_str}]"

        # Update the activity's title
        if "🎧📖" not in current_title:
            new_title = current_title + " 🎧📖"
        else:
            new_title = current_title
        
        update_activity(activity_id, new_title, new_description)
        return

    # --- If no ABS session, check for Last.fm scrobbles ---
    print("No ABS session found. Checking Last.fm...")
    
    try:
        activity_start_dt = datetime.datetime.strptime(last_activity["start_date"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
        activity_end_dt = activity_start_dt + datetime.timedelta(seconds=last_activity.get("elapsed_time", 0))
    except Exception as e:
        print(f"Error parsing activity time: {e}")
        return

    tracks = get_lastfm_tracks_for_window(activity_start_dt, activity_end_dt)
    
    if tracks:
        print(f"Found {len(tracks)} Last.fm scrobbles.")
        
        track_list_str = "\n".join([f"- {t}" for t in tracks])
        
        if current_description:
            new_description = current_description + "\n\n"
        else:
            new_description = ""
            
        # Add simple tracklist and profile link
        new_description += f"{track_list_str}\n\nhttps://www.last.fm/user/drahdiwaberl"

        if "🎧🤘🎵" not in current_title and "🎧📖" not in current_title:
             new_title = current_title + " 🎧🤘🎵"
        else:
            new_title = current_title

        update_activity(activity_id, new_title, new_description)
        return

    print("No ABS or Last.fm activity found for this timeframe.")

if __name__ == "__main__":
    main()