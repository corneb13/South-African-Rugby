from datetime import datetime, timezone, timedelta
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

FIXTURE_URL = "https://springboks.rugby/match-centre/fixtures"

def create_ics_event(summary, start_dt, end_dt, location, description, uid_id):
    fmt = "%Y%m%dT%H%M%SZ"
    return (
        "BEGIN:VEVENT\n"
        f"UID:sarugby-match-{uid_id}@sarugby\n"
        f"DTSTAMP:{datetime.now(timezone.utc).strftime(fmt)}\n"
        f"DTSTART:{start_dt.strftime(fmt)}\n"
        f"DTEND:{end_dt.strftime(fmt)}\n"
        f"SUMMARY:{summary}\n"
        f"LOCATION:{location}\n"
        f"DESCRIPTION:{description}\n"
        "STATUS:CONFIRMED\n"
        "END:VEVENT\n"
    )

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
        # Scroll to the bottom to trigger infinite scroll
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Look for any "Load More" buttons and click them
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
    events = []
    
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
                
                for offset in range(3, 8):
                    if idx + offset < len(lines):
                        check_line = lines[idx + offset]
                        if "," in check_line:
                            venue_info = check_line
                        elif any(k in check_line for k in ["Cup", "Division", "Shield", "Championship", "League"]):
                            comp_info = check_line

                sast_dt = datetime(current_date[0], current_date[1], current_date[2], hour, minute)
                utc_start = sast_dt - timedelta(hours=2)
                utc_start = utc_start.replace(tzinfo=timezone.utc)
                utc_end = utc_start + timedelta(hours=2)

                summary = f"🏉 {home_team} vs {away_team}"
                description = f"Tournament: {comp_info}\\nMatch: {home_team} v {away_team}"

                match_count += 1
                events.append(
                    create_ics_event(
                        summary=summary,
                        start_dt=utc_start,
                        end_dt=utc_end,
                        location=venue_info,
                        description=description,
                        uid_id=f"{current_date[0]}{current_date[1]:02d}{current_date[2]:02d}-{match_count}"
                    )
                )
            except Exception as e:
                print(f"Error parsing fixture around line {idx}: {e}")

        idx += 1

    ics_content = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//South African Rugby Fixtures//EN\n"
        "CALSCALE:GREGORIAN\n"
        "METHOD:PUBLISH\n"
        "X-WR-CALNAME:South African Rugby Fixtures\n"
        "X-WR-TIMEZONE:Africa/Johannesburg\n"
        + "".join(events)
        + "END:VCALENDAR\n"
    )

    with open("springboks.ics", "w", encoding="utf-8") as f:
        f.write(ics_content)
    print(f"Successfully generated springboks.ics with {len(events)} fixtures!")

if __name__ == "__main__":
    fetch_and_build_calendar()
