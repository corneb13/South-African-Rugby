from datetime import datetime, timezone, timedelta
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

FIXTURE_URL = "https://springboks.rugby/match-centre/fixtures"

def create_ics_event(summary, start_dt_utc, end_dt_utc, location, description, uid_id):
    fmt = "%Y%m%dT%H%M%SZ"
    dtstamp = datetime.now(timezone.utc).strftime(fmt)
    return (
        "BEGIN:VEVENT\n"
        f"UID:sarugby-springbok-{uid_id}@sarugby\n"
        f"DTSTAMP:{dtstamp}\n"
        f"DTSTART:{start_dt_utc.strftime(fmt)}\n"
        f"DTEND:{end_dt_utc.strftime(fmt)}\n"
        f"SUMMARY:{summary}\n"
        f"LOCATION:{location}\n"
        f"DESCRIPTION:{description}\n"
        "STATUS:CONFIRMED\n"
        "END:VEVENT\n"
    )

def format_team(team_name):
    flags = {
        "south africa": "🇿🇦", "springboks": "🇿🇦", "springbok": "🇿🇦",
        "new zealand": "🇳🇿", "all blacks": "🇳🇿",
        "australia": "🇦🇺", "wallabies": "🇦🇺",
        "argentina": "🇦🇷", "los pumas": "🇦🇷",
        "england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "ireland": "🇮🇪",
        "wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
        "france": "🇫🇷", "italy": "🇮🇹",
        "fiji": "🇫🇯", "samoa": "🇼🇸", "tonga": "🇹🇴",
        "japan": "🇯🇵", "georgia": "🇬🇪", "uruguay": "🇺🇾",
        "portugal": "🇵🇹", "spain": "🇪🇸", "usa": "🇺🇸",
        "canada": "🇨🇦", "namibia": "🇳🇦", "romania": "🇷🇴",
        "chile": "🇨🇱", "barbarians": "🏁"
    }
    
    lower_team = team_name.lower().strip()
    if lower_team in flags:
        return f"{flags[lower_team]} {team_name} 🏉"
        
    for key, flag in flags.items():
        if key in lower_team:
            return f"{flag} {team_name} 🏉"
            
    return f"🏳️ {team_name} 🏉"

def fetch_and_build_calendar():
    print("Starting headless browser...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(FIXTURE_URL)
    time.sleep(3)
    
    print("Scrolling to load all fixtures...")
    for _ in range(8): 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    events = []
    match_count = 0

    known_teams = {
        "springboks": "Springboks", "south africa": "South Africa",
        "new zealand": "New Zealand", "all blacks": "All Blacks",
        "australia": "Australia", "wallabies": "Wallabies",
        "argentina": "Argentina", "los pumas": "Los Pumas",
        "england": "England", "ireland": "Ireland", "wales": "Wales",
        "scotland": "Scotland", "france": "France", "italy": "Italy",
        "fiji": "Fiji", "samoa": "Samoa", "tonga": "Tonga",
        "japan": "Japan", "georgia": "Georgia", "uruguay": "Uruguay",
        "portugal": "Portugal", "spain": "Spain", "usa": "USA",
        "canada": "Canada", "namibia": "Namibia", "romania": "Romania",
        "chile": "Chile", "barbarians": "Barbarians"
    }

    # Extract text AND image alt tags to catch team logos
    elements = []
    for elem in soup.find_all(['p', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'img']):
        if elem.name == 'img' and elem.get('alt'):
            elements.append(elem['alt'].strip())
        elif elem.text and elem.text.strip():
            elements.append(elem.text.strip())

    lines = []
    for item in elements:
        if not lines or lines[-1] != item:
            lines.append(item)

    date_pattern = re.compile(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$')
    time_pattern = re.compile(r'^(\d{2}):(\d{2})$')

    current_date = None
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        
        date_match = date_pattern.match(line)
        if date_match:
            day_num = int(date_match.group(2))
            month_str = date_match.group(3)
            year_num = int(date_match.group(4))
            try:
                month_num = datetime.strptime(month_str, "%B").month
                current_date = (year_num, month_num, day_num)
            except ValueError:
                pass
            idx += 1
            continue

        time_match = time_pattern.match(line)
        if time_match and current_date:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))

            window = lines[idx+1 : idx+25]
            found_teams = []
            
            for token in window:
                token_lower = token.lower().strip()
                for key, canonical in known_teams.items():
                    if key in token_lower and canonical not in found_teams:
                        found_teams.append(canonical)
                        break

            if len(found_teams) >= 2:
                home_team = found_teams[0]
                away_team = found_teams[1]
            elif len(found_teams) == 1:
                home_team = found_teams[0]
                away_team = "TBD"
            else:
                home_team = "Springboks"
                away_team = "TBD"

            teams_text = f"{home_team.lower()} {away_team.lower()}"
            if "springbok" in teams_text or "south africa" in teams_text:
                # Convert SAST kickoff (17:10) to UTC (15:10) for standard calendar conversion
                sast_start = datetime(current_date[0], current_date[1], current_date[2], hour, minute)
                utc_start = (sast_start - timedelta(hours=2)).replace(tzinfo=timezone.utc)
                utc_end = utc_start + timedelta(hours=2)

                display_home = format_team(home_team)
                display_away = format_team(away_team)

                summary = f"{display_home} vs {display_away}"
                
                description = (
                    f"Tournament: International Fixture\\n"
                    f"Match: {display_home} v {display_away}\\n\\n"
                    f"Check GitHub: https://github.com/corneb13/South-African-Rugby/actions"
                )

                match_count += 1
                event_str = create_ics_event(
                    summary=summary,
                    start_dt_utc=utc_start,
                    end_dt_utc=utc_end,
                    location="South Africa",
                    description=description,
                    uid_id=f"{current_date[0]}{current_date[1]:02d}{current_date[2]:02d}-{match_count}"
                )
                events.append(event_str)
                idx += 8
                continue

        idx += 1

    ics_content = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Springboks Fixtures//EN\n"
        "CALSCALE:GREGORIAN\n"
        "METHOD:PUBLISH\n"
        "X-WR-CALNAME:Springboks Fixtures\n"
        "X-WR-TIMEZONE:Africa/Johannesburg\n"
        + "".join(events)
        + "END:VCALENDAR\n"
    )

    with open("springboks.ics", "w", encoding="utf-8") as f:
        f.write(ics_content)
        
    print(f"Successfully generated springboks.ics with {len(events)} Springbok fixtures!")

if __name__ == "__main__":
    fetch_and_build_calendar()
