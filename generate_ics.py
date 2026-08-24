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

    # Explicit Month Regex to prevent false matches on names like '10BET'
    MONTHS_REGEX = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|June|July|August|September|October|November|December)'
    
    month_year_pattern = re.compile(rf'^({MONTHS_REGEX})\s+(\d{{4}})$', re.IGNORECASE)
    date_pattern = re.compile(rf'^(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*[\s,]+)?(\d{{1,2}})\s+({MONTHS_REGEX})(?:[\s,]+(\d{{4}}))?$', re.IGNORECASE)
    time_pattern = re.compile(r'^([01]?\d|2[0-3])[:h]([0-5]\d)$')

    team_keywords = {
        "springboks": "Springboks", "springbok": "Springboks", "south africa": "Springboks",
        "new zealand": "New Zealand", "all blacks": "New Zealand",
        "australia": "Australia", "wallabies": "Australia",
        "argentina": "Argentina", "los pumas": "Argentina", "pumas": "Argentina",
        "england": "England", "ireland": "Ireland", "wales": "Wales",
        "scotland": "Scotland", "france": "France", "italy": "Italy",
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
                month_num = datetime.strptime(month_str[:3].title(), "%b").month
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
            text_block = " ".join(match_info)
            text_block_lower = text_block.lower()
            
            # STRICT FILTER: Ensure Springboks are part of this fixture block
            if "springbok" not in text_block_lower and "south africa" not in text_block_lower:
                idx += 1
                continue

            is_excluded = any(ex in text_block_lower for ex in ["women", "u20", "u21", "under 20", "under 21", "junior"])
            if not is_excluded:
                junk = ["v", "vs", "not started", "upcoming", "live", "ft", "full time", "match centre", "tbc", "tickets", "buy tickets", "view more", "find out more", "match info"]
                
                found_teams = []
                matches_in_block = []

                for kw, canonical in team_keywords.items():
                    pattern = rf'\b{re.escape(kw)}\b'
                    for match in re.finditer(pattern, text_block_lower):
                        matches_in_block.append((match.start(), canonical))
                
                matches_in_block.sort(key=lambda x: x[0])
                
                for pos, canonical in matches_in_block:
                    if canonical not in found_teams:
                        found_teams.append(canonical)

                if len(found_teams) >= 2:
                    home_team = found_teams[0]
                    away_team = found_teams[1]
                elif len(found_teams) == 1:
                    if found_teams[0] == "Springboks":
                        home_team = "Springboks"
                        away_team = "TBD"
                    else:
                        home_team = found_teams[0]
                        away_team = "Springboks"
                else:
                    home_team = "Springboks"
                    away_team = "TBD"

                other_lines = []
                for item in match_info:
                    item_clean = item.strip()
                    item_lower = item_clean.lower()
                    if item_lower in junk:
                        continue
                    if any(kw in item_lower for kw in team_keywords.keys()):
                        continue
                    if item_clean and item_clean not in other_lines:
                        other_lines.append(item_clean)

                venue = "South Africa"
                tournament = "International Fixture"

                for info in other_lines:
                    info_lower = info.lower()
                    if any(kw in info_lower for kw in ["stadium", "park", "ellis", "loftus", "kings", "arena", "field", "stadion", "stade", "aviva", "twickenham", "murrayfield", "optus", "allianz", "fnb", "dhl", "m&t"]):
                        venue = info.title() if info.isupper() else info
                        break

                for info in other_lines:
                    if info != venue and len(info) > 3:
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
        
    print(f"Successfully generated springboks.ics with {len(events)} correctly parsed Springbok fixtures!")

if __name__ == "__main__":
    fetch_and_build_calendar()
