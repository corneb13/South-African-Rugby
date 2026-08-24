from datetime import datetime, timezone, timedelta
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

FIXTURE_URL = "https://www.world.rugby/tournaments/fixtures-results"

def create_ics_event(summary, start_dt, end_dt, location, description, uid_id):
    fmt = "%Y%m%dT%H%M%S"
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:worldrugby-springbok-{uid_id}@worldrugby",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;TZID=Africa/Johannesburg:{start_dt.strftime(fmt)}",
        f"DTEND;TZID=Africa/Johannesburg:{end_dt.strftime(fmt)}",
        f"SUMMARY:{summary}",
        f"LOCATION:{location}",
        f"DESCRIPTION:{description}",
        "STATUS:CONFIRMED",
        "END:VEVENT"
    ])

def format_team(team_name):
    flags = {
        "south africa": "🇿🇦", "springboks": "🇿🇦", "rsa": "🇿🇦",
        "new zealand": "🇳🇿", "all blacks": "🇳🇿", "nzl": "🇳🇿",
        "australia": "🇦🇺", "wallabies": "🇦🇺", "aus": "🇦🇺",
        "argentina": "🇦🇷", "los pumas": "🇦🇷", "arg": "🇦🇷",
        "england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "eng": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "ireland": "🇮🇪", "ire": "🇮🇪",
        "wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "wal": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
        "scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "sco": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
        "france": "🇫🇷", "fra": "🇫🇷",
        "italy": "🇮🇹", "ita": "🇮🇹",
        "fiji": "🇫🇯", "fij": "🇫🇯",
        "japan": "🇯🇵", "jpn": "🇯🇵"
    }
    team_lower = team_name.lower().strip()
    flag = flags.get(team_lower, "🏳️")
    return f"{flag} {team_name.title()} 🏉"

def main():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

    driver = webdriver.Chrome(options=options)
    driver.get(FIXTURE_URL)
    time.sleep(6)  # Give World Rugby's react frontend time to hydrate
    page_source = driver.page_source
    driver.quit()

    soup = BeautifulSoup(page_source, 'html.parser')
    
    # World Rugby fixtures container parser
    events = []
    seen_fixtures = set()

    # Extract match elements or fallback to structured text blocks
    text_blocks = soup.get_text(separator="\n").splitlines()
    clean_lines = [line.strip() for line in text_blocks if line.strip()]

    # Pattern matchers
    time_pattern = re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$')
    date_pattern = re.compile(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})$', re.IGNORECASE)

    months_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }

    current_date = None

    for idx, line in enumerate(clean_lines):
        d_match = date_pattern.match(line)
        if d_match:
            day = int(d_match.group(2))
            m_str = d_match.group(3)[:3].lower()
            year = int(d_match.group(4))
            if m_str in months_map:
                current_date = (year, months_map[m_str], day)
            continue

        t_match = time_pattern.match(line)
        if t_match and current_date:
            hour, minute = int(t_match.group(1)), int(t_match.group(2))
            
            # Context window around the timestamp
            context = " ".join(clean_lines[max(0, idx-4):min(len(clean_lines), idx+5)])
            context_lower = context.lower()

            if "south africa" in context_lower or "springboks" in context_lower or " rsa " in f" {context_lower} ":
                # Extract opponent
                teams_found = []
                known_teams = ["South Africa", "New Zealand", "Australia", "Argentina", "England", "Ireland", "Wales", "Scotland", "France", "Italy", "Fiji", "Japan"]
                
                for team in known_teams:
                    if team.lower() in context_lower:
                        teams_found.append(team)

                home = teams_found[0] if len(teams_found) > 0 else "South Africa"
                away = teams_found[1] if len(teams_found) > 1 else ("Springboks" if home != "South Africa" else "TBD")

                fixture_key = f"{current_date[0]}-{current_date[1]}-{current_date[2]}-{hour}:{minute}"

                if fixture_key not in seen_fixtures:
                    seen_fixtures.add(fixture_key)
                    start_dt = datetime(current_date[0], current_date[1], current_date[2], hour, minute)
                    end_dt = start_dt + timedelta(hours=2)

                    summary = f"{format_team(home)} vs {format_team(away)}"
                    
                    events.append(
                        create_ics_event(summary, start_dt, end_dt, "World Rugby Event", "Source: World Rugby", fixture_key)
                    )

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//World Rugby//Springboks Fixtures//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Springboks Rugby",
        "X-WR-TIMEZONE:Africa/Johannesburg",
        *events,
        "END:VCALENDAR"
    ]

    with open("springboks.ics", "w", encoding="utf-8") as f:
        f.write("\n".join(ics_content))

    print(f"Generated springboks.ics with {len(seen_fixtures)} matches from World Rugby.")

if __name__ == "__main__":
    main()
