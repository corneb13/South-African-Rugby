import sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

def create_ics_event(summary, start_dt_utc, end_dt_utc, location="", description="", uid_id=""):
    fmt = "%Y%m%dT%H%M%SZ"
    dtstamp = datetime.now(timezone.utc).strftime(fmt)
    lines = [
        "BEGIN:VEVENT",
        f"UID:springboks-15s-{uid_id}@sarugby",
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

def format_team(team_name):
    clean = team_name.strip().title()
    flags = {
        "South Africa": "🇿🇦", "Springboks": "🇿🇦",
        "New Zealand": "🇳🇿", "All Blacks": "🇳🇿",
        "Australia": "🇦🇺", "Wallabies": "🇦🇺",
        "Argentina": "🇦🇷", "Pumas": "🇦🇷",
        "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Ireland": "🇮🇪", 
        "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", 
        "France": "🇫🇷", "Italy": "🇮🇹", 
        "Fiji": "🇫🇯", "Japan": "🇯🇵"
    }
    flag = flags.get(clean, "🏉")
    return f"{flag} {clean}"

def main():
    print("Launching browser to fetch official SA Rugby Match Centre fixtures...")
    captured_matches = []

    def handle_response(response):
        if response.status == 200 and "json" in response.headers.get("content-type", ""):
            try:
                data = response.json()
                if isinstance(data, dict):
                    content = data.get("content", [])
                    if isinstance(content, list) and content and "teams" in content[0]:
                        captured_matches.extend(content)
                        print(f"Intercepted SA Rugby fixture payload ({len(content)} matches).")
            except Exception:
                pass

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page.on("response", handle_response)

            # Target official SA Rugby site
            url = "https://www.springboks.rugby/match-centre/"
            print(f"Navigating to {url}...")
            page.goto(url, wait_until="networkidle", timeout=35000)
            page.wait_for_timeout(4000)

            browser.close()
    except Exception as e:
        print(f"Browser execution note: {e}")

    events = []
    seen = set()

    for match in captured_matches:
        teams = match.get("teams", [])
        if not isinstance(teams, list) or len(teams) < 2:
            continue

        t1_name = teams[0].get("name", "") if isinstance(teams[0], dict) else ""
        t2_name = teams[1].get("name", "") if isinstance(teams[1], dict) else ""
        
        # Verify senior Springboks involvement
        combined_names = f"{t1_name} {t2_name}"
        if not any(k in combined_names for k in ["South Africa", "Springboks"]):
            continue

        time_info = match.get("time", {})
        ts_ms = time_info.get("millis") if isinstance(time_info, dict) else None
        if not ts_ms:
            continue

        start_dt_utc = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        match_key = f"{t1_name}-{t2_name}-{start_dt_utc.timestamp()}"

        if match_key in seen:
            continue
        seen.add(match_key)

        end_dt_utc = start_dt_utc + timedelta(hours=2)
        sast_dt = start_dt_utc.astimezone(ZoneInfo("Africa/Johannesburg"))

        venue_info = match.get("venue", {})
        venue = venue_info.get("name", "") if isinstance(venue_info, dict) else ""
        comp_info = match.get("tournament", {})
        comp = comp_info.get("name", "") if isinstance(comp_info, dict) else ""

        summary = f"{format_team(t1_name)} vs {format_team(t2_name)}"
        match_id = match.get("matchId", f"{start_dt_utc.timestamp()}")

        events.append(create_ics_event(summary, start_dt_utc, end_dt_utc, venue, comp, match_id))
        print(f"Added match: {summary} on {sast_dt.strftime('%Y-%m-%d %H:%M SAST')}")

    print(f"Total official Springboks events compiled: {len(events)}")

    if not events:
        print("ERROR: No Springboks events compiled. Aborting calendar update.")
        sys.exit(1)

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Springboks Official Fixtures//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Springboks Rugby",
        *events,
        "END:VCALENDAR"
    ]

    with open("springboks.ics", "w", encoding="utf-8") as f:
        f.write("\n".join(ics_content))

    print("File springboks.ics successfully updated with official matches.")

if __name__ == "__main__":
    main()
