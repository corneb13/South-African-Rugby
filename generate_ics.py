import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

API_URL = "https://cmsapi.pulselive.com/rugby/match"

def create_ics_event(summary, start_dt_utc, end_dt_utc, uid_id):
    # Pure UTC format ending with 'Z' lets Apple/Google Calendar auto-convert to SAST (17:00)
    fmt_utc = "%Y%m%dT%H%M%SZ"
    dtstamp = datetime.now(timezone.utc).strftime(fmt_utc)
    
    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:worldrugby-{uid_id}@rugby",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start_dt_utc.strftime(fmt_utc)}",
        f"DTEND:{end_dt_utc.strftime(fmt_utc)}",
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.world.rugby",
        "Referer": "https://www.world.rugby/"
    }
    
    # Range query: From today through 1 year ahead
    now = datetime.now(timezone.utc)
    start_date_str = now.strftime("%Y-%m-%d")
    end_date_str = (now + timedelta(days=365)).strftime("%Y-%m-%d")

    page = 0
    max_pages = 10

    while page < max_pages:
        params = {
            "client": "worldrugby",
            "sport": "rugbyu",
            "startDate": start_date_str,
            "endDate": end_date_str,
            "sort": "ASC",
            "page": page,
            "pageSize": 50
        }

        try:
            response = requests.get(API_URL, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            matches = data.get("content", [])
            if not matches:
                break

            for match in matches:
                try:
                    teams = match.get("teams", [])
                    if len(teams) != 2:
                        continue
                        
                    team1 = teams[0].get("name", "TBD")
                    team2 = teams[1].get("name", "TBD")

                    if "South Africa" in team1 or "South Africa" in team2:
                        time_info = match.get("time", {})
                        timestamp_ms = time_info.get("millis")
                        if not timestamp_ms:
                            continue

                        # Read direct UTC epoch
                        start_dt_utc = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
                        end_dt_utc = start_dt_utc + timedelta(hours=2)

                        # Print local SAST in logs to confirm correct 17:00 time
                        sast_dt = start_dt_utc.astimezone(ZoneInfo("Africa/Johannesburg"))

                        summary = f"{format_team(team1)} vs {format_team(team2)}"
                        match_id = match.get("matchId", f"{team1}-{team2}-{start_dt_utc.year}")

                        events.append(create_ics_event(summary, start_dt_utc, end_dt_utc, match_id))
                        print(f"Added: {summary} on {sast_dt.strftime('%Y-%m-%d %H:%M SAST')}")
                        
                except Exception as e:
                    print(f"Error parsing match: {e}")
                    continue

            page_info = data.get("pageInfo", {})
            num_pages = page_info.get("numPages", 1)
            page += 1
            if page >= num_pages:
                break

        except Exception as e:
            print(f"Failed to fetch page {page}: {e}")
            break

    if not events:
        print("No upcoming South Africa matches found in date range.")

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

    print(f"File springboks.ics successfully generated with {len(events)} matches.")

if __name__ == "__main__":
    main()
