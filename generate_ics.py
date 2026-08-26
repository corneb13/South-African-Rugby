import sys
import json
import re
import requests
from html.parser import HTMLParser
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_script = False
        self.script_data = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script and data.strip():
            self.script_data.append(data.strip())

def extract_json_objects(text):
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(text):
        match = re.search(r'[\{\[]', text[pos:])
        if not match:
            break
        start = pos + match.start()
        try:
            obj, end = decoder.raw_decode(text[start:])
            yield obj
            pos = start + max(end, 1)
        except Exception:
            pos = start + 1

def find_matches_recursive(obj, matches_list):
    if isinstance(obj, dict):
        if "teams" in obj and isinstance(obj["teams"], list) and len(obj["teams"]) >= 2:
            matches_list.append(obj)
        for v in obj.values():
            find_matches_recursive(v, matches_list)
    elif isinstance(obj, list):
        for item in obj:
            find_matches_recursive(item, matches_list)

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
    print("Loading World Rugby fixtures web page...")
    url = "https://www.world.rugby/fixtures"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        print(f"Page Load Status Code: {response.status_code}")
        response.raise_for_status()

        parser = ScriptParser()
        parser.feed(response.text)

        candidate_matches = []
        for script_content in parser.script_data:
            if any(k in script_content for k in ["South Africa", "Springboks", "RSA"]):
                for json_obj in extract_json_objects(script_content):
                    find_matches_recursive(json_obj, candidate_matches)

        print(f"Extracted {len(candidate_matches)} raw match candidates from JavaScript state.")

        events = []
        seen_matches = set()

        for match in candidate_matches:
            teams = match.get("teams", [])
            if not isinstance(teams, list) or len(teams) < 2:
                continue

            t1_name = teams[0].get("name", "") if isinstance(teams[0], dict) else str(teams[0])
            t2_name = teams[1].get("name", "") if isinstance(teams[1], dict) else str(teams[1])
            t1_abbr = teams[0].get("abbreviation", "") if isinstance(teams[0], dict) else ""
            t2_abbr = teams[1].get("abbreviation", "") if isinstance(teams[1], dict) else ""

            search_str = f"{t1_name} {t2_name} {t1_abbr} {t2_abbr}"
            if any(k in search_str for k in ["South Africa", "Springboks", "RSA"]):
                time_info = match.get("time") or match.get("date") or {}
                timestamp_ms = time_info.get("millis") if isinstance(time_info, dict) else None
                
                if not timestamp_ms and isinstance(match.get("timestamp"), (int, float)):
                    timestamp_ms = match.get("timestamp")

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
                match_id = match.get("matchId") or match.get("id") or f"{start_dt_utc.timestamp()}"

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

    except Exception as e:
        print(f"Execution Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
