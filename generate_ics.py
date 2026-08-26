import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

API_URL = "https://cmsapi.pulselive.com/rugby/match"

def create_ics_event(summary, start_dt_utc, end_dt_utc, uid_id):
    fmt = "%Y%m%dT%H%M%SZ"
    dtstamp = datetime.now(timezone.utc).strftime(fmt)
    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:worldrugby-{uid_id}@rugby",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start_dt_utc.strftime(fmt)}",
        f"DTEND:{end_dt_utc.strftime(fmt)}",
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
    print("Fetching fixtures from World Rugby API...")
    events = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.world.rugby",
        "Referer": "https://www.world.rugby/"
    }

    params = {
        "client": "worldrugby",
        "sport": "rugbyu",
        "pageSize": 100
    }

    try:
        response = requests.get(API_URL, headers=headers, params=params, timeout=15)
        print(f"API Response Status Code: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        
        matches = data.get("content", [])
        print(f"Total matches retrieved from API: {len(matches)}")

        for match in matches:
            teams = match.get("teams", [])
            if len(teams) < 2:
                continue
                
            t1_name = teams[0].get("name", "")
            t2_name = teams[1].get("name", "")
            t1_abbr = teams[0].get("abbreviation", "")
            t2_abbr = teams[1].get("abbreviation", "")

            # Match against name or abbreviation (RSA)
            search_str = f"{t1_name} {t2_name} {t1_abbr} {t2_abbr}"
            if any(k in search_str for k in ["South Africa", "Springboks", "RSA"]):
                time_info = match.get("time", {})
                timestamp_ms = time_info.get("millis")
                if not timestamp_ms:
                    continue

                start_dt_utc = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
                end_dt_utc = start_dt_utc + timedelta(hours=2)

                sast_dt = start_dt_utc.astimezone(ZoneInfo("Africa/Johannesburg"))
                summary = f"{format_team(t1_name)} vs {format_team(t2_name)}"
                match_id = match.get("matchId", f"{start_dt_utc.timestamp()}")

                events.append(create_ics_event(summary, start_dt_utc, end_dt_utc, match_id))
                print(f"Found match: {summary} on {sast_dt.strftime('%Y-%m-%d %H:%M SAST')}")

    except Exception as e:
        print(f"API Fetch Error: {e}")

    print(f"Total Springboks events compiled: {len(events)}")

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Springboks API Fixtures//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Springboks Rugby",
        *events,
        "END:VCALENDAR"
    ]

    with open("springboks.ics", "w", encoding="utf-8") as f:
        f.write("\n".join(ics_content))

if __name__ == "__main__":
    main()
