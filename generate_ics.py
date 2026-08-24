from datetime import datetime, timezone, timedelta
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
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
        "chile": "🇨🇱", "british & irish lions": "🦁", "barbarians": "🏁"
    }
    
    lower_team = team_name.lower().strip()
    if lower_team in flags:
        return f"{flags[lower_team]} {team_name} 🏉"
        
    for key, flag in flags.items():
        if key in lower_team:
            return f"{flag} {team_name} 🏉"
            
    return f"🏳️ {team_name} 🏉"

def fetch_and_build_calendar():
    print("Starting headless browser with SAST timezone override...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": "Africa/Johannesburg"})
    
    driver.get(FIXTURE_URL)
    time.sleep(3)
    
    print("Scrolling to load complete fixture list...")
    for _ in range(10): 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        try:
            buttons = driver.find_elements(By.XPATH, "//button | //a")
            for btn in buttons:
                text = btn.text.strip().lower()
                if "load more" in text or "show more" in text:
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1.5)
        except Exception:
            pass

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    for img in soup.find_all('img'):
        alt_text = img.get('alt', '').strip()
        if alt_text:
            img.replace_with(f" {alt_text} ")

    raw_lines = [line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip()]
    lines = []
    for l in raw_lines:
        if not lines or lines[-1].lower() != l.lower():
            lines.append(l)

    events = []
    current_year = datetime.now().year
    current_date = None
    seen_fixtures = set()

    month_year_pattern = re.compile(r'^(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{4})$', re.IGNORECASE)
    date_pattern = re.compile(r'^(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*[\s,]+)?(\d{1,2})\s+([A-Za-z]+)(?:[\s,]+(\d{4}))?$', re.IGNORECASE)
    time_pattern = re.compile(r'^(\d{1,2})[:h](\d{2})$')

    team_keywords = {
        "springboks": "Springboks", "springbok": "Springboks", "south africa": "Springboks",
        "all blacks": "New Zealand", "new zealand": "New Zealand",
        "wallabies": "Australia", "australia": "Australia",
        "los pumas": "Argentina", "argentina": "Argentina",
        "england": "England", "ireland": "Ireland",
        "wales": "Wales", "scotland": "Scotland",
        "france": "France", "italy": "Italy",
        "fiji": "Fiji", "samoa": "Samoa", "tonga": "Tonga",
        "japan": "Japan", "georgia": "Georgia", "uruguay": "Uruguay",
        "portugal": "Portugal", "spain": "Spain", "usa": "USA",
        "canada": "Canada", "namibia": "Namibia", "romania": "Romania",
        "chile": "Chile", "british & irish lions": "British & Irish Lions", "barbarians": "Barbarians"
    }

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        
        my_match = month_year_pattern.match(line)
        if my_match:
            current_year = int(my_match.group(2))
            idx += 1
            continue

        date_match = date_pattern.match(line)
        if date_match and not my_match:
            day_num = int(date_match.group(1))
            month_str = date_match.group(2)
            year_num = int(date_match.group(3)) if date_match.group(3) else current_year
            try:
                month_num = datetime.strptime(month_str[:3], "%b").month
                current_date = (year_num, month_num, day_num)
            except ValueError:
                pass
            idx += 1
            continue

        time_match = time_pattern.match(line)
        if time_match and current_date:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))

            match_info = []
            offset = 1
            while idx + offset < len(lines):
                nxt = lines[idx + offset]
                if time_pattern.match(nxt) or date_pattern.match(nxt) or month_year_pattern.match(nxt):
                    break
                match_info.append(nxt)
                offset += 1

            idx += offset - 1
            text_block = " ".join(match_info).lower()
            
            # STRICT FILTER
            if "springbok" not in text_block and "south africa" not in text_block:
                idx += 1
                continue

            is_excluded = any(ex in text_block for ex in ["women", "u20", "u21", "under 20", "under 21", "junior"])
            if not is_excluded:
                junk = ["v", "vs", "not started", "upcoming", "live", "ft", "full time", "match centre", "tbc", "tickets", "buy tickets", "view more", "find out more", "match info"]
                
                found_teams = []
                other_info = []

                for item in match_info:
                    item_lower = item.lower().strip()
                    if item_lower in junk:
                        continue
                    
                    # Prevent venue names from causing a false team match
                    safe_item = item_lower.replace("stade de france", "sdf_venue")
                    
                    teams_in_line = []
                    for kw, canonical in team_keywords.items():
                        position = safe_item.find(kw)
                        if position != -1:
                            teams_in_line.append((position, canonical))
                            
                    if teams_in_line:
                        # Sort by their position in the sentence to maintain Home v Away order
                        teams_in_line.sort(key=lambda x: x[0])
                        for pos, canonical in teams_in_line:
                            if canonical not in found_teams:
                                found_teams.append(canonical)
                    else:
                        if item.strip() and item.strip() not in other_info:
                            other_info.append(item.strip())

                if "Springboks" not in found_teams:
                    found_teams.append("Springboks")

                if len(found_teams) >= 2:
                    home_team = found_teams[0]
                    away_team = found_teams[1]
                else:
                    home_team = found_teams[0]
                    away_team = "TBD"

                venue = "South Africa"
                tournament = "International Fixture"

                for info in other_info:
                    lower_info = info.lower()
                    if any(kw in lower_info for kw in ["stadium", "park", "ellis", "loftus", "kings", "arena", "field", "stadion", "stade", "aviva", "twickenham", "murrayfield"]):
                        venue = info.title() if info.isupper() else info
                        break

                for info in other_info:
                    if info != venue and len(info) > 4:
                        tournament = info.title() if info.isupper() else info
                        break

                fixture_key = f"{current_date[0]}-{current_date[1]}-{current_date[2]}-{hour}:{minute}-{home_team}-{away_team}"
                if fixture_key not in seen_fixtures:
                    seen_fixtures.add(fixture_key)

                    sast_start = datetime(current_date[0], current_date[1], current_date[2], hour, minute)
                    sast_end = sast_start + timedelta(hours=2)

                    display_home = format_team(home_team)
                    display_away = format_team(away_team)

                    summary = f"{display_home} vs {display_away}"
                    description = (
                        f"Tournament: {tournament}\\n"
                        f"Match: {display_home} v {display_away}\\n\\n"
                        f"Check GitHub Feed: https://github.com/corneb13/South-African-Rugby/actions"
                    )

                    event_str = create_ics_event(
                        summary=summary,
                        start_dt=sast_start,
                        end_dt=sast_end,
                        location=venue,
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
        
    print(f"Successfully generated springboks.ics with {len(events)} correctly formatted fixtures!")

if __name__ == "__main__":
    fetch_and_build_calendar()
