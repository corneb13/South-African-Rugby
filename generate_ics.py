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
        "chile": "🇨🇱", "british & irish lions": "🦁", "barbarians": "🐑"
    }
    team_lower = team_name.lower()
    flag = flags.get(team_lower, "🏳️") 
    return f"{flag} {team_name} 🏉"

def main():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    
    driver = webdriver.Chrome(options=options)
    driver.get(FIXTURE_URL)
    time.sleep(3) 
    page_source = driver.page_source
    driver.quit()

    soup = BeautifulSoup(page_source, 'html.parser')

    # Convert images to their alt text AND file names to catch hidden logos
    for img in soup.find_all('img'):
        alt_text = img.get('alt', '').strip()
        src_text = img.get('src', '').strip()
        try:
            filename = src_text.split('/')[-1].split('.')[0]
            filename = re.sub(r'[^a-zA-Z0-9]', ' ', filename)
        except Exception:
            filename = ""
        img.replace_with(f" {alt_text} {filename} ")

    raw_text = soup.get_text(separator="\n")
    raw_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    # Filter purely numeric lines unless they are days (1-31) or times
    lines = []
    for line in raw_lines:
        if line.isdigit():
            if not (1 <= int(line) <= 31):
                continue
        lines.append(line)

    date_pattern = re.compile(r'^(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})$')
    month_year_pattern = re.compile(r'^([A-Za-z]{3,})\s+(\d{4})$')
    time_pattern = re.compile(r'^([01]?\d|2[0-3])[:h]([0-5]\d)$')

    months_map = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
        "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
    }

    # Added extensive abbreviation mappings
    team_keywords = {
        "springboks": "Springboks", "springbok": "Springboks", "south africa": "Springboks", "rsa": "Springboks", "za": "Springboks",
        "new zealand": "New Zealand", "all blacks": "New Zealand", "nzl": "New Zealand", "nz": "New Zealand",
        "australia": "Australia", "wallabies": "Australia", "aus": "Australia",
        "argentina": "Argentina", "los pumas": "Argentina", "pumas": "Argentina", "arg": "Argentina",
        "england": "England", "eng": "England", "ireland": "Ireland", "ire": "Ireland",
        "wales": "Wales", "wal": "Wales", "scotland": "Scotland", "sco": "Scotland",
        "france": "France", "fra": "France", "italy": "Italy", "ita": "Italy",
        "fiji": "Fiji", "fij": "Fiji", "samoa": "Samoa", "sam": "Samoa", "tonga": "Tonga", "ton": "Tonga",
        "japan": "Japan", "jpn": "Japan", "georgia": "Georgia", "geo": "Georgia",
        "uruguay": "Uruguay", "uru": "Uruguay", "portugal": "Portugal", "por": "Portugal",
        "spain": "Spain", "esp": "Spain", "usa": "USA", "canada": "Canada", "can": "Canada",
        "namibia": "Namibia", "nam": "Namibia", "romania": "Romania", "rom": "Romania",
        "chile": "Chile", "chi": "Chile",
        "british & irish lions": "British & Irish Lions", "british and irish lions": "British & Irish Lions", "lions": "British & Irish Lions", "bil": "British & Irish Lions",
        "barbarians": "Barbarians"
    }

    junk = ["v", "vs", "not started", "upcoming", "live", "ft", "full time", "match centre", "tbc", "tickets", "buy tickets", "view more", "find out more", "match info", "sast"]

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SA Rugby//Springboks Fixtures//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Springboks Rugby",
        "X-WR-TIMEZONE:Africa/Johannesburg"
    ]

    current_date = None
    seen_fixtures = set()
    idx = 0

    while idx < len(lines):
        line = lines[idx]

        d_match = date_pattern.match(line)
        if d_match:
            day = int(d_match.group(1))
            m_str = d_match.group(2).lower()
            year = int(d_match.group(3))
            if m_str in months_map:
                current_date = (year, months_map[m_str], day)
            idx += 1
            continue

        my_match = month_year_pattern.match(line)
        if my_match:
            if idx > 0 and lines[idx-1].isdigit() and 1 <= int(lines[idx-1]) <= 31:
                day = int(lines[idx-1])
                m_str = my_match.group(1).lower()
                year = int(my_match.group(2))
                if m_str in months_map:
                    current_date = (year, months_map[m_str], day)
            idx += 1
            continue

        time_match = time_pattern.match(line)
        if time_match and current_date:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))

            match_info = []

            # READ BACKWARDS up to 5 lines to catch teams listed before the time
            back_offset = 1
            while idx - back_offset >= 0 and back_offset <= 5:
                prev = lines[idx - back_offset]
                if time_pattern.match(prev) or date_pattern.match(prev) or month_year_pattern.match(prev):
                    break
                match_info.insert(0, prev) 
                back_offset += 1

            # READ FORWARDS up to 5 lines to catch teams/venues listed after the time
            offset = 1
            while idx + offset < len(lines) and offset <= 6:
                nxt = lines[idx + offset]
                if time_pattern.match(nxt) or date_pattern.match(nxt) or month_year_pattern.match(nxt):
                    break
                match_info.append(nxt)
                offset += 1

            text_block = " ".join(match_info)
            text_block_lower = text_block.lower()
            
            # Create a robust, space-padded block stripped of punctuation for safe matching
            clean_text_block = re.sub(r'[^a-z0-9]', ' ', text_block_lower)
            padded_search = f" {clean_text_block} "

            # STRICT FILTER: Ensure Springboks are playing
            is_springbok_match = any(f" {kw} " in padded_search for kw in ["springboks", "springbok", "south africa", "rsa", "za"])
            
            if not is_springbok_match:
                idx += offset - 1
                idx += 1
                continue

            matches_in_block = []
            for kw, canonical in team_keywords.items():
                safe_kw = f" {re.sub(r'[^a-z0-9]', ' ', kw)} "
                start = 0
                while True:
                    pos = padded_search.find(safe_kw, start)
                    if pos == -1:
                        break
                    matches_in_block.append((pos, canonical))
                    start = pos + 1

            matches_in_block.sort(key=lambda x: x[0])
            
            found_teams = []
            for pos, canonical in matches_in_block:
                if canonical not in found_teams:
                    found_teams.append(canonical)

            if len(found_teams) == 0:
                found_teams.append("Springboks")

            home_team = found_teams[0]
            away_team = found_teams[1] if len(found_teams) > 1 else "TBD"

            other_lines = []
            for item in match_info:
                item_clean = item.strip()
                item_lower = item_clean.lower()
                if item_lower in junk:
                    continue
                
                # Verify the line isn't just a team name/acronym before classifying it as a venue
                is_team_line = False
                item_padded = f" {re.sub(r'[^a-z0-9]', ' ', item_lower)} "
                for kw in team_keywords.keys():
                    safe_kw = f" {re.sub(r'[^a-z0-9]', ' ', kw)} "
                    if safe_kw in item_padded:
                        is_team_line = True
                        break
                
                if is_team_line:
                    continue
                
                if item_clean and item_clean not in other_lines:
                    other_lines.append(item_clean)

            venue = " / ".join(other_lines) if other_lines else "South Africa"

            fixture_key = f"{current_date[0]}-{current_date[1]}-{current_date[2]}-{hour}:{minute}-{home_team}-{away_team}"
            
            if fixture_key not in seen_fixtures:
                seen_fixtures.add(fixture_key)
                
                start_dt = datetime(current_date[0], current_date[1], current_date[2], hour, minute)
                end_dt = start_dt + timedelta(hours=2)

                summary = f"{format_team(home_team)} vs {format_team(away_team)}"
                uid_id = f"{fixture_key.replace(' ', '').replace(':', '')}"

                ics_content.append(
                    create_ics_event(summary, start_dt, end_dt, venue, "Scraped from springboks.rugby", uid_id)
                )

            idx += offset - 1
            
        idx += 1

    ics_content.append("END:VCALENDAR")

    with open("springboks.ics", "w", encoding="utf-8") as f:
        f.write("\n".join(ics_content))

    print(f"Generated springboks.ics with {len(seen_fixtures)} matches.")

if __name__ == "__main__":
    main()
