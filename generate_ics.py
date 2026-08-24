from datetime import datetime, timezone, timedelta
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
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
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    print("Fetching World Rugby fixtures...")
    driver = webdriver.Chrome(options=options)
    driver.get(FIXTURE_URL)
    
    time.sleep(8) 
    
    # Try to close cookie consent if it exists (it can block clicks)
    try:
        driver.execute_script("""
            var cookieBtn = document.querySelector('#onetrust-accept-btn-handler');
            if(cookieBtn) cookieBtn.click();
        """)
        time.sleep(1)
    except:
        pass

    print("Scrolling and loading future dates...")
    # Scroll and click 'Load More' 5 times to get future fixtures
    for _ in range(5):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        try:
            driver.execute_script("""
                let buttons = Array.from(document.querySelectorAll('button'));
                let loadMore = buttons.find(b => b.textContent.toLowerCase().includes('load') || b.textContent.toLowerCase().includes('more'));
                if (loadMore) loadMore.click();
            """)
            time.sleep(3)
        except Exception:
            break

    page_source = driver.page_source
    driver.quit()

    soup = BeautifulSoup(page_source, 'html.parser')
    events = []
    seen_fixtures = set()

    text_blocks = soup.get_text(separator="\n").splitlines()
    clean_lines = [line.strip() for line in text_blocks if line.strip()]

    time_pattern = re.compile(r'\b([01]?\d|2[0-3]):([0-5]\d)\b')
    date_pattern = re.compile(r'\b(\d{1,2})\s+([A-Za-z]{3,})(?:\s+(\d{4}))?\b', re.IGNORECASE)

    months_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }

    current_date = None
    current_year_fallback = datetime.now().year

    for idx, line in enumerate(clean_lines):
        d_match = date_pattern.search(line)
        if d_match:
            day = int(d_match.group(1))
            m_str = d_match.group(2)[:3].lower()
            year = int(d_match.group(3)) if d_match.group(3) else current_year_fallback
            
            if m_str in months_map:
                current_date = (year, months_map[m_str], day)
            continue

        t_match = time_pattern.search(line)
        if t_match and current_date:
            hour, minute = int(t_match.group(1)), int(t_match.group(2))
            
            context = " ".join(clean_lines[max(0, idx-6):min(len(clean_lines), idx+7)])
            context_lower = context.lower()

            # Filter out Women's, Under 20s, and Sevens matches
            if any(k in context_lower for k in ["women", "u20", "sevens", " 7s ", "under 20"]):
                continue

            if "south africa" in context_lower or "springboks" in context_lower or " rsa " in f" {context_lower} ":
                teams_found = []
                known_teams = ["South Africa", "New Zealand", "Australia", "Argentina", "England", "Ireland", "Wales", "Scotland", "France", "Italy", "Fiji", "Japan"]
                
                for team in known_teams:
                    if team.lower() in context_lower:
                        teams_found.append(team)

                teams_found = list(dict.fromkeys(teams_found))

                home = teams_found[0] if len(teams_found) > 0 else "South Africa"
                away = teams_found[1] if len(teams_found) > 1 else ("Springboks" if home != "South Africa" else "TBD")

                # The Fix: We removed the time from the fixture key. 
                # This ensures we only log one event per day for these specific teams.
                fixture_key = f"{current_date[0]}-{current_date[1]}-{current_date[2]}-{home}-{away}"

                if fixture_key not in seen_fixtures:
                    seen_fixtures.add(fixture_key)
                    start_dt = datetime(current_date[0], current_date[1], current_date[2], hour, minute)
                    end_dt = start_dt + timedelta(hours=2)

                    summary = f"{format_team(home)} vs {format_team(away)}"
                    
                    # We strip the spaces to make a valid UID
                    uid = fixture_key.replace(" ", "")
                    
                    events.append(
                        create_ics_event(summary, start_dt, end_dt, "World Rugby Event", "Source: World Rugby", uid)
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
