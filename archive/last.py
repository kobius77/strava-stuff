import requests
import datetime
import pytz

# Last.fm credentials
LASTFM_API_KEY = "44198e285e5181099f1e3f30a2d1de94"
LASTFM_USER = "drahdiwaberl"
LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"

def get_lastfm_tracks_for_window(start_time, end_time):
    """
    Fetches all scrobbled tracks from Last.fm within a given time window.
    
    Args:
        start_time (datetime.datetime): The start of the time window (UTC).
        end_time (datetime.datetime): The end of the time window (UTC).
        
    Returns:
        A list of strings, e.g., ["Artist - TrackName", ...], or None.
    """
    
    # Convert datetime objects to Unix timestamps (which Last.fm API requires)
    from_timestamp = int(start_time.timestamp())
    to_timestamp = int(end_time.timestamp())

    payload = {
        "method": "user.getRecentTracks",
        "user": LASTFM_USER,
        "api_key": LASTFM_API_KEY,
        "from": from_timestamp,
        "to": to_timestamp,
        "format": "json",
        "limit": 200  # Max allowed by API is 200 per page
    }
    
    try:
        response = requests.get(LASTFM_API_URL, params=payload)
        response.raise_for_status()  # Raises an HTTPError for bad responses
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Last.fm: {e}")
        return None

    data = response.json()
    
    # Check if 'recenttracks' or 'track' key exists
    if "recenttracks" not in data or "track" not in data["recenttracks"]:
        print("Last.fm response OK, but no 'recenttracks' key found.")
        print(data)
        return None

    tracks = data["recenttracks"]["track"]
    
    if not tracks:
        print("No tracks scrobbled in this time window.")
        return None

    # Handle the case where only one track is returned (it's not a list)
    if not isinstance(tracks, list):
        tracks = [tracks]

    # Format the tracks. We want to ignore "now playing" tracks.
    # We will also reverse the list so it's in chronological order.
    formatted_tracks = []
    for track in reversed(tracks):
        # Ignore "now playing" track, which has no date
        if "@attr" in track and track["@attr"].get("nowplaying") == "true":
            continue
            
        artist = track.get("artist", {}).get("#text", "Unknown Artist")
        name = track.get("name", "Unknown Track")
        formatted_tracks.append(f"{artist} - {name}")
        
    # De-duplicate the list while preserving order
    unique_tracks = []
    seen = set()
    for item in formatted_tracks:
        if item not in seen:
            unique_tracks.append(item)
            seen.add(item)

    return unique_tracks

# --- Main test block ---
if __name__ == "__main__":
    print("Testing Last.fm API connection...")
    
    local_tz = pytz.timezone("Europe/Vienna")
    
    # Using the specific run times you just provided:
    # Today (Nov 9, 2025) from 19:13 to 19:25
    today = datetime.datetime.now(local_tz)
    test_start_time = today.replace(hour=19, minute=13, second=0, microsecond=0)
    test_end_time = today.replace(hour=19, minute=25, second=0, microsecond=0)

    # Convert to UTC for the function
    test_start_utc = test_start_time.astimezone(pytz.utc)
    test_end_utc = test_end_time.astimezone(pytz.utc)

    print(f"Checking for scrobbles between:")
    print(f"  {test_start_time.strftime('%Y-%m-%d %H:%M:%S')} (Vienna)")
    print(f"  {test_start_utc.strftime('%Y-%m-%d %H:%M:%S')} (UTC)")
    print(f"  and")
    print(f"  {test_end_time.strftime('%Y-%m-%d %H:%M:%S')} (Vienna)")
    print(f"  {test_end_utc.strftime('%Y-%m-%d %H:%M:%S')} (UTC)")
    print("---")

    tracks = get_lastfm_tracks_for_window(test_start_utc, test_end_utc)
    
    if tracks:
        print(f"Found {len(tracks)} unique tracks:")
        for i, track_name in enumerate(tracks):
            print(f"  {i+1:02d}. {track_name}")
    else:
        print("No tracks found for the test window.")