import requests
from datetime import datetime, timezone, timedelta

# World Rugby's backend API (Powered by PulseLive)
# statuses=U (Unplayed)
API_URL = "https://cmsapi.pulselive.com/rugby/match"

def create_ics_event(summary, start_dt, end_dt, uid_id):
    fmt = "%Y%m%dT%H%M%S"
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:worldrugby-{uid_id}@rugby",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;TZID=Africa/Johannesburg:{start_dt.strftime(fmt)}",
        f"DTEND;TZID=Africa/Johannesburg:{end_dt.strftime(fmt)}",
        f"SUMMARY:{summary}",
        "DESCRIPTION:Source: World Rugby API",
        "STATUS:CONFIRMED",
        "END:VEVENT"
    ])

def format_team(team_name):
    flags = {
        "South Africa": "🇿🇦", "New Zealand": "🇳🇿", "Australia": "🇦🇺", 
        "Argentina": "🇦🇷", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Ireland": "🇮🇪", 
        "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "France": "🇫🇷", 
        "Italy": "🇮🇹", "Fiji": "🇫🇯", "Japan": "🇯🇵"
    }
    flag = flags.get(team_name, "🏉")
    return f"{flag} {team_name}"

def main():
    print("Fetching fixtures directly from World Rugby API...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Origin": "https://www.world.rugby",
        "Referer": "https://www.world.rugby/"
    }
    
    # We query all upcoming Men's matches (sport=rugbyu, statuses=U)
    params = {
        "client": "worldrugby",
        "sport": "rugbyu",
        "statuses": "U", # U = Unplayed (Future matches)
        "page": 0,
        "pageSize": 100
    }

    try:
        response = requests.get(API_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Failed to fetch data from API: {e}")
        return

    events = []
    
    # PulseLive stores the list of matches inside the 'content' array
    matches = data.get("content", [])
    print(f"Found {len(matches)} total upcoming global rugby matches.")

    for match in matches:
        try:
            # Check if this is a Men's 15s match (ignoring Women's, Sevens, U20)
            # You can inspect match['events'] or match['competition'] if needed
            teams = match.get("teams", [])
            if len(teams) != 2:
                continue
                
            team1 = teams[0].get("name", "TBD")
            team2 = teams[1].get("name", "TBD")

            # Is South Africa playing?
            if "South Africa" in team1 or "South Africa" in team2:
                # The API provides time in standard milliseconds since epoch! 
                # No more regex parsing for dates/times!
                timestamp_ms = match.get("time", {}).get("millis")
                
                if not timestamp_ms:
                    continue

                # Convert UTC timestamp to our timezone
                start_dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
                end_dt = start_dt + timedelta(hours=2)

                summary = f"{format_team(team1)} vs {format_team(team2)}"
                match_id = match.get("matchId", f"{team1}-{team2}-{start_dt.year}")

                events.append(create_ics_event(summary, start_dt, end_dt, match_id))
                print(f"Added: {summary} on {start_dt.strftime('%Y-%m-%d %H:%M')}")
                
        except Exception as e:
            print(f"Error parsing a match: {e}")
            continue

    if not events:
        print("No upcoming South Africa matches found in the API feed.")
        return

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Springboks API Fixtures//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Springboks Rugby",
        "X-WR-TIMEZONE:Africa/Johannesburg",
        *events,
        "END:VCALENDAR"
    ]

    with open("springboks_api.ics", "w", encoding="utf-8") as f:
        f.write("\n".join(ics_content))

    print(f"Successfully generated springboks_api.ics with {len(events)} matches.")

if __name__ == "__main__":
    main()
