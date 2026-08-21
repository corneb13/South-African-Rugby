from datetime import datetime, timezone, timedelta
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

FIXTURE_URL = "https://springboks.rugby/match-centre/fixtures"

def create_ics_event(summary, start_dt, end_dt, location, description, uid_id):
    fmt = "%Y%m%dT%H%M%S"
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        "BEGIN:VEVENT\n"
        f"UID:sarugby-springbok-{uid_id}@sarugby\n"
        f"DTSTAMP:{dtstamp}\n"
        f"DTSTART;TZID=Africa/Johannesburg:{start_dt.strftime(fmt)}\n"
        f"DTEND;TZID=Africa/Johannesburg:{end_dt.strftime(fmt)}\n"
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
    print("Starting browser session...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(FIXTURE_URL)
    time.sleep(3)
    
    print("Scrolling to load complete fixture list...")
    for _ in range(6): 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    # Extract page text split cleanly by lines
    raw_lines = [line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip()]
    
    # Deduplicate consecutive identical lines to prevent event multiplying
    lines = []
    for l in raw_lines:
        if not lines or lines[-1] != l:
            lines.append(l)

    events = []
    current_date = None
    seen_fixtures = set()

    date_pattern = re.compile(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$')
    time_pattern = re.compile(r'^(\d{2}):(\d{2})$')

    known_teams = [
        "springboks", "south africa", "new zealand", "all blacks", "australia", "wallabies",
        "argentina", "los pumas", "england", "ireland", "wales", "scotland", "france", "italy",
        "fiji", "samoa", "tonga", "japan", "georgia", "uruguay", "portugal", "spain", "usa",
        "canada", "namibia", "romania", "chile", "barbarians"
    ]

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

            # Look forward up to 15 lines for teams and match context
            chunk = lines[idx+1 : idx+16]
            
            found_teams = []
            for item in chunk:
                item_lower = item.lower()
                for kt in known_teams:
                    if kt in item_lower:
                        # Normalize common names
                        clean_name = item
                        if "springbok" in item_lower or "south africa" in item_lower:
                            clean_name = "Springboks"
                        elif "new zealand" in item_lower or "all black" in item_lower:
                            clean_name = "New Zealand"
                        elif "australia" in item_lower or "wallab" in item_lower:
                            clean_name = "Australia"
                        elif "argentina" in item_lower or "pumas" in item_lower:
                            clean_name = "Argentina"
                            
                        if clean_name not in found_teams:
                            found_teams.append(clean_name)

            if "Springboks" in found_teams or any(kt in " ".join(found_teams).lower() for kt in ["south africa", "springbok"]):
                home_team = found_teams[0] if len(found_teams) > 0 else "Springboks"
                away_team = found_teams[1] if len(found_teams) > 1 else ("Opponent" if home_team == "Springboks" else "Springboks")
                
                # Prevent duplicate entries for the exact same match slot
                fixture_key = f"{current_date}-{hour}:{minute}-{home_team}-{away_team}"
                if fixture_key not in seen_fixtures:
                    seen_fixtures.add(fixture_key)

                    sast_start = datetime(current_date[0], current_date[1], current_date[2], hour, minute)
                    sast_end = sast_start + timedelta(hours=2)

                    display_home = format_team(home_team)
                    display_away = format_team(away_team)

                    summary = f"{display_home} vs {display_away}"
                    description = (
                        f"Match: {display_home} v {display_away}\\n\\n"
                        f"Check GitHub Feed: https://github.com/corneb13/South-African-Rugby/actions"
                    )

                    event_str = create_ics_event(
                        summary=summary,
                        start_dt=sast_start,
                        end_dt=sast_end,
                        location="South Africa",
                        description=description,
                        uid_id=f"{current_date[0]}{current_date[1]:02d}{current_date[2]:02d}-{hour}{minute}"
                    )
                    events.append(event_str)

        idx += 1

    ics_content = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Springboks Fixtures//EN\n"
        "CALSCALE:GREGORIAN\n"
        "METHOD:PUBLISH\n"
        "X-WR-CALNAME:Springboks Fixtures\n"
        "X-WR-TIMEZONE:Africa/Johannesburg\n"
        "BEGIN:VTIMEZONE\n"
        "TZID:Africa/Johannesburg\n"
        "X-LIC-LOCATION:Africa/Johannesburg\n"
        "BEGIN:STANDARD\n"
        "TZOFFSETFROM:+0200\n"
        "TZOFFSETTO:+0200\n"
        "TZNAME:SAST\n"
        "DTSTART:19700101T000000\n"
        "END:STANDARD\n"
        "END:VTIMEZONE\n"
        + "".join(events)
        + "END:VCALENDAR\n"
    )

    with open("springboks.ics", "w", encoding="utf-8") as f:
        f.write(ics_content)
        
    print(f"Successfully generated springboks.ics with {len(events)} Springbok fixtures!")

if __name__ == "__main__":
    fetch_and_build_calendar()
