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
    options.add_argument('--headless=new') # Better headless mode to avoid bot detection
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    # Add a realistic User-Agent so World Rugby doesn't block the request
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    print("Fetching World Rugby fixtures...")
    driver = webdriver.Chrome(options=options)
    driver.get(FIXTURE_URL)
    
    # Give it a bit more time to hydrate, just in case
    time.sleep(8) 
    page_source = driver.page_source
    driver.quit()

    # --- DEBUGGING STEP ---
    # Save the HTML to a file so you can visually verify if the page loaded correctly
    # and if the Springboks are actually present in the HTML structure.
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(page_source)
    print("Saved 'debug_page.html'. If no fixtures are found, open this file to see what the scraper actually saw.")

    soup = BeautifulSoup(page_source, 'html.parser')
    events = []
    seen_fixtures = set()

    text_blocks = soup.get_text(separator="\n").splitlines()
    clean_lines = [line.strip() for line in text_blocks if line.strip()]

    # Relaxed pattern matchers (removed ^ and $ so it finds the pattern anywhere in the line)
    time_pattern = re.compile(r'\b([01]?\d|2[0-3]):([0-5]\d)\b')
    # Made year optional, as the site might just say "24 Aug"
    date_pattern = re.compile(r'\b(\d{1,2})\s+([A-Za-z]{3,})(?:\s+(\d{4}))?\b', re.IGNORECASE)

    months_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }

    current_date = None
    current_year_fallback = datetime.now().year

    for idx, line in enumerate(clean_lines):
        d_match = date_pattern.search(line) # Changed to .search()
        if d_match:
            day = int(d_match.group(1))
            m_str = d_match.group(2)[:3].lower()
            # Use the year if provided, otherwise assume the current year
            year = int(d_match.group(3)) if d_match.group(3) else current_year_fallback
            
            if m_str in months_map:
                current_date = (year, months_map[m_str], day)
            continue

        t_match = time_pattern.search(line) # Changed to .search()
        if t_match and current_date:
            hour, minute = int(t_match.group(1)), int(t_match.group(2))
            
            # Widen context window slightly just in case React spaces things out
            context = " ".join(clean_lines[max(0, idx-6):min(len(clean_lines), idx+7)])
            context_lower = context.lower()

            if "south africa" in context_lower or "springboks" in context_lower or " rsa " in f" {context_lower} ":
                teams_found = []
                known_teams = ["South Africa", "New Zealand", "Australia", "Argentina", "England", "Ireland", "Wales", "Scotland", "France", "Italy", "Fiji", "Japan"]
                
                for team in known_teams:
                    if team.lower() in context_lower:
                        teams_found.append(team)

                # Deduplicate teams found just in case a team is mentioned twice
                teams_found = list(dict.fromkeys(teams_found))

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

    if not events:
        print("No Springbok matches found. Check 'debug_page.html' to see if the matches are actually listed on the default URL load.")
        return

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
