import sys
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}

def is_senior_springboks_match(home, away):
    h = home.upper()
    a = away.upper()
    
    # Must involve the Springboks or South Africa
    has_bok = "SPRINGBOK" in h or "SPRINGBOK" in a or "SOUTH AFRICA" in h or "SOUTH AFRICA" in a
    if not has_bok:
        return False
        
    # Exclude non-Senior Men's teams (Women, U20, U21, 7s, internal squads)
    exclusions = ["WOMEN", "U20", "U21", "U18", "7S", "SEVENS", "GIRLS", "BOYS", "XXIII", "GEN", "BOLTS", "XV"]
    for x in exclusions:
        if x in h or x in a:
            return False
            
    return True

def format_team(name):
    upper = name.strip().upper()
    if "SPRINGBOK" in upper or "SOUTH AFRICA" in upper:
        return "🇿🇦 Springboks"
    elif "NEW ZEALAND" in upper or "ALL BLACKS" in upper:
        return "🇳🇿 New Zealand"
    elif "AUSTRALIA" in upper or "WALLABIES" in upper:
        return "🇦🇺 Australia"
    elif "ARGENTINA" in upper or "PUMAS" in upper:
        return "🇦🇷 Argentina"
    elif "ITALY" in upper:
        return "🇮🇹 Italy"
    elif "FRANCE" in upper:
        return "🇫🇷 France"
    elif "IRELAND" in upper:
        return "🇮🇪 Ireland"
    elif "ENGLAND" in upper:
        return "🏴󠁧󠁢󠁥󠁮󠁧󠁿 England"
    elif "WALES" in upper:
        return "🏴󠁧󠁢󠁷󠁬󠁳󠁿 Wales"
    elif "SCOTLAND" in upper:
        return "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotland"
    elif "JAPAN" in upper:
        return "🇯🇵 Japan"
    elif "FIJI" in upper:
        return "🇫🇯 Fiji"
    return f"🏉 {name.strip().title()}"

def create_ics_event(summary, start_dt_utc, end_dt_utc, location="", description="", uid_id=""):
    fmt = "%Y%m%dT%H%M%SZ"
    dtstamp = datetime.now(timezone.utc).strftime(fmt)
    lines = [
        "BEGIN:VEVENT",
        f"UID:springboks-test-{uid_id}@sarugby",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start_dt_utc.strftime(fmt)}",
        f"DTEND:{end_dt_utc.strftime(fmt)}",
        f"SUMMARY:{summary}",
    ]
    if location:
        lines.append(f"LOCATION:{location}")
    if description:
        lines.append(f"DESCRIPTION:{description}")
    lines.extend([
        "STATUS:CONFIRMED",
        "END:VEVENT"
    ])
    return "\n".join(lines)

def parse_dom_text(page_text):
    events = []
    seen = set()
    sast_tz = ZoneInfo("Africa/Johannesburg")
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    
    current_year = datetime.now().year
    current_month = None

    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Detect Month / Year headers like "AUGUST 2026"
        header_m = re.search(r'^(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{4})$', line, re.IGNORECASE)
        if header_m:
            current_month = MONTH_MAP[header_m.group(1).lower()]
            current_year = int(header_m.group(2))
            i += 1
            continue

        # Detect Date lines like "Sat 29 Aug" or "29 Aug"
        date_m = re.search(r'^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$', line, re.IGNORECASE)
        if date_m:
            day = int(date_m.group(1))
            month = MONTH_MAP[date_m.group(2).lower()]
            year = current_year if current_year else datetime.now().year
            
            block = lines[i+1 : i+12]
            time_str = "15:00"
            team_home, team_away = "", ""
            venue, tournament = "", ""

            for b_idx, b_line in enumerate(block):
                time_m = re.search(r'^(\d{1,2}:\d{2})$', b_line)
                if time_m:
                    time_str = time_m.group(1)

                vs_m = re.search(r'^(.+?)\s+[Vv]\s+(.+?)$', b_line)
                if vs_m:
                    team_home = vs_m.group(1).strip()
                    team_away = vs_m.group(2).strip()
                    if b_idx + 1 < len(block):
                        venue = block[b_idx + 1]
                    if b_idx + 2 < len(block):
                        tournament = block[b_idx + 2]
                elif b_line.upper() in ["V", "VS"] and b_idx > 0 and b_idx + 1 < len(block):
                    team_home = block[b_idx - 1].strip()
                    team_away = block[b_idx + 1].strip()
                    if b_idx + 2 < len(block):
                        venue = block[b_idx + 2]
                    if b_idx + 3 < len(block):
                        tournament = block[b_idx + 3]

            # Enforce Senior Springboks Filtering
            if team_home and team_away and is_senior_springboks_match(team_home, team_away):
                key = f"{team_home}-{team_away}-{year}-{month}-{day}"
                if key not in seen:
                    seen.add(key)
                    hour, minute = map(int, time_str.split(":"))
                    dt_sast = datetime(year, month, day, hour, minute, tzinfo=sast_tz)
                    dt_utc = dt_sast.astimezone(timezone.utc)
                    end_dt_utc = dt_utc + timedelta(hours=2)

                    summary = f"{format_team(team_home)} vs {format_team(team_away)}"
                    match_id = f"{year}{month:02d}{day:02d}-{hour:02d}{minute:02d}"

                    events.append(create_ics_event(summary, dt_utc, end_dt_utc, venue, tournament, match_id))
                    print(f"Added Test Match: {summary} on {dt_sast.strftime('%Y-%m-%d %H:%M SAST')}")

        i += 1

    return events

def main():
    print("Launching browser to fetch SA Rugby Match Centre fixtures...")
    events = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900}
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            url = "https://www.springboks.rugby/match-centre/"
            print(f"Navigating to {url}...")
            page.goto(url, wait_until="networkidle", timeout=35000)
            
            # Scroll to trigger loading of all upcoming fixtures
            for _ in range(10):
                page.evaluate("window.scrollBy(0, 800)")
                page.wait_for_timeout(500)

            full_text = page.inner_text("body")
            events = parse_dom_text(full_text)
            browser.close()
    except Exception as e:
        print(f"Browser execution note: {e}")

    print(f"Total Senior Springboks Test events compiled: {len(events)}")

    if not events:
        print("ERROR: No Senior Springboks Test events compiled. Aborting calendar update.")
        sys.exit(1)

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Springboks Official Test Fixtures//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Springboks Rugby",
        *events,
        "END:VCALENDAR"
    ]

    with open("springboks.ics", "w", encoding="utf-8") as f:
        f.write("\n".join(ics_content))

    print("File springboks.ics successfully updated with official Senior Test matches.")

if __name__ == "__main__":
    main()
