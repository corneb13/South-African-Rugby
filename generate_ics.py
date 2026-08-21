from datetime import datetime, timezone, timedelta
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

FIXTURE_URL = "https://springboks.rugby/match-centre/fixtures"

def create_ics_event(summary, start_dt_utc, end_dt_utc, location, description, uid_id):
    # Using 'Z' format enforces standard UTC, allowing subscriber calendar apps 
    # to automatically convert event times to their local device timezone.
    fmt = "%Y%m%dT%H%M%SZ"
    dtstamp = datetime.now(timezone.utc).strftime(fmt)
    return (
        "BEGIN:VEVENT\n"
        f"UID:sarugby-match-{uid_id}@sarugby\n"
        f"DTSTAMP:{dtstamp}\n"
        f"DTSTART:{start_dt_utc.strftime(fmt)}\n"
        f"DTEND:{end_dt_utc.strftime(fmt)}\n"
        f"SUMMARY:{summary}\n"
        f"LOCATION:{location}\n"
        f"DESCRIPTION:{description}\n"
        "STATUS:CONFIRMED\n"
        "END:VEVENT\n"
    )

def sanitize_filename(name):
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', name)
    return clean.strip().replace(' ', '_').lower() + '.ics'

def format_team(team_name):
    flags = {
        "south africa": "🇿🇦", "springboks": "🇿🇦",
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
        "chile": "🇨🇱", "british & irish lions": "🦁",
        "zimbabwe": "🇿🇼", "kenya": "🇰🇪"
    }
    
    lower_team = team_name.lower().strip()
    
    if lower_team in flags:
        return f"{flags[lower_team]} {team_name} 🏉"
        
    for key, flag in flags.items():
        if lower_team.startswith(key):
            return f"{flag} {team_name} 🏉"
            
    return None

def fetch_and_build_calendar():
    print("Starting headless browser...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(FIXTURE_URL)
    
    print("Scrolling and expanding page to load all future fixtures...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    for _ in range(12): 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        try:
            buttons = driver.find_elements(By.XPATH, "//button | //a")
            for btn in buttons:
                text = btn.text.strip().lower()
                if "load more" in text or "show more" in text:
                    driver.execute_script("arguments[0].scrollIntoView();", btn)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(2)
        except Exception:
            pass

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    print("Page fully loaded. Extracting HTML...")
    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, "html.parser")
    
    calendars = {}
    
    current_date = None
    match_count = 0

    page_text = soup.get_text(separator="\n")
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]

    date_pattern = re.compile(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$')
    time_pattern = re.compile(r'^(\d{2}):(\d{2})$')

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

            try:
                home_team = lines[idx + 1] if idx + 1 < len(lines) else "TBD"
                away_team = lines[idx + 3] if idx + 3 < len(lines) else "TBD"
                
                if home_team == lines[idx + 2] if idx + 2 < len(lines) else "":
                    away_team = lines[idx + 4] if idx + 4 < len(lines) else away_team

                venue_info = "South Africa"
                comp_info = "SA Rugby Fixture" 
                
                comp_keywords = ["Cup", "Division", "Shield", "Championship", "League", "Test", "Tour", "Series", "International"]
                intl_keywords = ["Test", "Tour", "Series", "International", "Championship", "World Cup"]
                
                for offset in range(3, 8):
                    if idx + offset < len(lines):
                        check_line = lines[idx + offset]
                        if "," in check_line:
                            venue_info = check_line
                        elif any(k in check_line for k in comp_keywords):
                            comp_info = check_line

                # Convert local SAST time (UTC+2) to standard UTC
                sast_dt = datetime(current_date[0], current_date[1], current_date[2], hour, minute)
                utc_start = (sast_dt - timedelta(hours=2)).replace(tzinfo=timezone.utc)
                utc_end = utc_start + timedelta(hours=2)

                # Emoji formatting for international fixtures
                display_home = home_team
                display_away = away_team
                is_international = any(k in comp_info for k in intl_keywords)
                
                if is_international:
                    h_fmt = format_team(home_team)
                    a_fmt = format_team(away_team)
                    
                    if h_fmt or a_fmt:
                        display_home = h_fmt if h_fmt else f"🏳️ {home_team} 🏉"
                        display_away = a_fmt if a_fmt else f"🏳️ {away_team} 🏉"

                summary = f"{display_home} vs {display_away}"
                
                description = (
                    f"Tournament: {comp_info}\\n"
                    f"Match: {display_home} v {display_away}\\n\\n"
                    f"Need to update subscriptions?\\n"
                    f"Check GitHub: https://github.com/corneb13/South-African-Rugby/actions"
                )

                match_count += 1
                event_str = create_ics_event(
                    summary=summary,
                    start_dt_utc=utc_start,
                    end_dt_utc=utc_end,
                    location=venue_info,
                    description=description,
                    uid_id=f"{current_date[0]}{current_date[1]:02d}{current_date[2]:02d}-{match_count}"
                )
                
                if comp_info not in calendars:
                    calendars[comp_info] = []
                calendars[comp_info].append(event_str)
                
            except Exception as e:
                print(f"Error parsing fixture around line {idx}: {e}")

        idx += 1

    for comp_name, events_list in calendars.items():
        filename = sanitize_filename(comp_name)
        
        ics_content = (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            f"PRODID:-//South African Rugby - {comp_name}//EN\n"
            "CALSCALE:GREGORIAN\n"
            "METHOD:PUBLISH\n"
            f"X-WR-CALNAME:{comp_name}\n"
            "X-WR-TIMEZONE:Africa/Johannesburg\n"
            + "".join(events_list)
            + "END:VCALENDAR\n"
        )

        with open(filename, "w", encoding="utf-8") as f:
            f.write(ics_content)
            
        print(f"Successfully generated {filename} with {len(events_list)} fixtures!")

if __name__ == "__main__":
    fetch_and_build_calendar()
