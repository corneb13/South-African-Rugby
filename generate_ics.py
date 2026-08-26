import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

TARGET_API = "https://cmsapi.pulselive.com/rugby/match?client=worldrugby&sport=rugbyu&pageSize=100&language=en"

# High-availability proxy chain
ENDPOINTS = [
    f"https://corsproxy.io/?{requests.utils.quote(TARGET_API, safe='')}",
    f"https://api.codetabs.com/v1/proxy?quest={requests.utils.quote(TARGET_API, safe='')}",
    TARGET_API
]

def create_ics_event(summary, start_dt_utc, end_dt_utc, uid_id):
    fmt = "%Y%m%dT%H%M%SZ"
    dtstamp = datetime.now(timezone.utc).strftime(fmt)
    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:springboks-{uid_id}@rugby",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start_dt_utc.strftime(fmt)}",
        f"DTEND:{end_dt_utc.strftime(fmt)}",
        f"SUMMARY:{summary}",
        "DESCRIPTION:Source: World Rugby",
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    data = None
    for url in ENDPOINTS:
        try:
            domain_label = url.split('/')[2]
            print(f"Attempting fetch via proxy [{domain_label}]...")
            response = requests.get(url, headers=headers, timeout=8)
            
            if response.status_code == 200:
                raw_data = response.json()
                data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                print(f"Success via [{domain_label}]!")
                break
            else:
                print(f"Proxy [{domain_label}] returned status {response.status_code}")
        except Exception as e:
            print(f"Proxy failed: {e}")
            continue

    if not data:
        print("ERROR: All proxy endpoints failed or timed out. Aborting update.")
        sys.exit(1)

    matches = data.get("content", [])
    print(f"Total matches retrieved: {len(matches)}")

    events = []
    for match in matches:
        teams = match.get("teams", [])
        if not isinstance(teams, list) or len(teams) < 2:
            continue

        t1_name = teams[0].get("name", "") if isinstance(teams[0], dict) else ""
        t2_name = teams[1].get("name", "") if isinstance(teams[1], dict) else ""
        t1_abbr = teams[0].get("abbreviation", "") if isinstance(teams[0], dict) else ""
        t2_abbr = teams[1].get("abbreviation", "") if isinstance(teams[1], dict) else ""

        search_str = f"{t1_name} {t2_name} {t1_abbr} {t2_abbr}"
        if any(k in search_str for k in ["South Africa", "Springboks", "RSA"]):
            time_info = match.get("time", {})
            timestamp_ms = time_info.get("millis") if isinstance(time_info, dict) else None
            if not timestamp_ms:
                continue

            start_dt_utc = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
            end_dt_utc = start_dt_utc + timedelta(hours=2)

            sast_dt = start_dt_utc.astimezone(ZoneInfo("Africa/Johannesburg"))
            summary = f"{format_team(t1_name)} vs {format_team(t2_name)}"
            match_id = match.get("matchId", f"{start_dt_utc.timestamp()}")

            events.append(create_ics_event(summary, start_dt_utc, end_dt_utc, match_id))
            print(f"Added match: {summary} on {sast_dt.strftime('%Y-%m-%d %H:%M SAST')}")

    print(f"Total Springboks events compiled: {len(events)}")

    if not events:
        print("ERROR: No Springboks events compiled. Aborting calendar update.")
        sys.exit(1)

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Springboks Fixtures//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Springboks Rugby",
        *events,
        "END:VCALENDAR"
    ]

    with open("springboks.ics", "w", encoding="utf-8") as f:
        f.write("\n".join(ics_content))

    print("File springboks.ics successfully updated.")

if __name__ == "__main__":
    main()
