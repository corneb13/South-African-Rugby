import sys
import re
import json
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

URL = "https://www.world.rugby/fixtures"

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

def extract_matches_from_html(html_text):
    matches = []
    # Find inline JSON state embedded in script tags
    script_pattern = re.compile(r'<script[^>]*>(.*?)</script>', re.DOTALL)
    
    for script in script_pattern.findall(html_text):
        if "South Africa" in script or "RSA" in script:
            # Look for JSON structures containing match arrays
            match_json = re.findall(r'\{"matchId":.*?\}(?=\s*[,\]\}])', script)
            for m_str in match_json:
                try:
                    data = json.loads(m_str)
                    matches.append(data)
                except Exception:
                    continue
    return matches

def main():
    print("Loading World Rugby fixtures web page...")
    events = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }

    try:
        response = requests.get(URL, headers=headers, timeout=20)
        print(f"Page Load Status Code: {response.status_code}")
        response.raise_for_status()
        
        matches = extract_matches_from_html(response.text)
        print(f"Found {len(matches)} matching fixture payloads in page data.")

        seen_matches = set()
        for match in matches:
            teams = match.get("teams", [])
            if len(teams) < 2:
                continue

            t1_name = teams[0].get("name", "")
            t2_name = teams[1].get("name", "")
            t1_abbr = teams[0].get("abbreviation", "")
            t2_abbr = teams[1].get("abbreviation", "")

            search_str = f"{t1_name} {t2_name} {t1_abbr} {t2_abbr}"
            if any(k in search_str for k in ["South Africa", "Springboks", "RSA"]):
                timestamp_ms = match.get("time", {}).get("millis")
                if not timestamp_ms:
                    continue

                start_dt_utc = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
                match_key = f"{t1_name}-{t2_name}-{start_dt_utc.timestamp()}"
                
                if match_key in seen_matches:
                    continue
                seen_matches.add(match_key)

                end_dt_utc = start_dt_utc + timedelta(hours=2)
                sast_dt = start_dt_utc.astimezone(ZoneInfo("Africa/Johannesburg"))

                summary = f"{format_team(t1_name)} vs {format_team(t2_name)}"
                match_id = match.get("matchId", f"{start_dt_utc.timestamp()}")

                events.append(create_ics_event(summary, start_dt_utc, end_dt_utc, match_id))
                print(f"Added match: {summary} on {sast_dt.strftime('%Y-%m-%d %H:%M SAST')}")

    except Exception as e:
        print(f"Extraction Error: {e}")

    print(f"Total Springboks events compiled: {len(events)}")

    if not events:
        print("ERROR: No events extracted from web page. Aborting calendar update.")
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
