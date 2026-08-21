from datetime import datetime, timezone, timedelta
import re
import requests
from bs4 import BeautifulSoup

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
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(FIXTURE_URL, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch site, status code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    events = []

    # Find match containers or text blocks on the page
    # SA Rugby renders dates followed by match rows
    current_date = None
    match_count = 0

    # Extract all text elements to iterate through fixtures sequentially
    page_text = soup.get_text(separator="\n")
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]

    # Pattern match for dates like "Friday, 21 August 2026"
    date_pattern = re.compile(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$')
    # Pattern match for kick-off times like "04:00" or "17:05"
    time_pattern = re.compile(r'^(\d{2}):(\d{2})$')

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        
        # Check for date headers
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

        # Look for time indicators starting a fixture entry
        time_match = time_pattern.match(line)
        if time_match and current_date:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))

            # Attempt to gather match details following the time
            # Structure: Home Team, Away Team, Venue/Competition
            try:
                home_team = lines[idx + 1] if idx + 1 < len(lines) else "TBD"
                away_team = lines[idx + 3] if idx + 3 < len(lines) else "TBD"
                
                # Filter out system duplicate labels
                if home_team == lines[idx + 2] if idx + 2 < len(lines) else "":
                    away_team = lines[idx + 4] if idx + 4 < len(lines) else away_team

                venue_info = "South Africa"
                comp_info = "SA Rugby Fixture"
                
                # Search next few lines for venue & competition name
                for offset in range(3, 8):
                    if idx + offset < len(lines):
                        check_line = lines[idx + offset]
                        if "," in check_line:  # Venues usually contain commas e.g. "Stadium, City"
                            venue_info = check_line
                        elif "Cup" in check_line or "Division" in check_line or "Shield" in check_line or "Championship" in check_line:
                            comp_info = check_line

                # Convert SAST (UTC+2) to UTC for standard calendar specs
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

    # Fallback to direct HTML block parsing if text stream yields empty
    if not events:
        for card in soup.find_all(["div", "article", "tr"]):
            text = card.get_text()
            if " vs " in text or " V " in text or "Not Started" in text:
                # Basic fallback entry generator
                pass

    # Build full ICS content
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
