import sys
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

def create_ics_event(summary, start_dt_utc, end_dt_utc, uid_id):
    fmt = "%Y%m%dT%H%M%SZ"
    dtstamp = datetime.now(timezone.utc).strftime(fmt)
    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:springboks-{uid_id}@rugby",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{start_dt_utc.strftime(fmt)}",
        f"DTEND:{end_dt_utc.strftime(fmt)}",
        f"SUMMARY:{summary}",
        "DESCRIPTION:Source: World Rugby",
        "STATUS:CONFIRMED",
        "END:VEVENT"
    ])

def format_team(team_name):
    flags = {
        "South Africa": "🇿🇦", "New Zealand": "🇳🇿", "Australia": "🇦🇺", 
        "Argentina": "🇦🇷", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Ireland": "🇮🇪", 
        "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "France": "🇫🇷", 
        "Italy": "🇮🇹", "Fiji": "🇫🇯", "Japan": "🇯🇵"
    }
    flag = flags.get(team_name, "🏉")
    return f"{flag} {team_name}"

def main():
    print("Launching stealth browser instance...")
    captured_matches = []

    def handle_response(response):
        # Capture any JSON payload containing match arrays
        if response.status == 200 and "json" in response.headers.get("content-type", ""):
            try:
                data = response.json()
                if isinstance(data, dict):
                    content = data.get("content", [])
                    if isinstance(content, list) and content and "teams" in content[0]:
                        captured_matches.extend(content)
                        print(f"Intercepted fixture stream from: {response.url[:60]}... ({len(content)} matches)")
            except Exception:
                pass

    try:
        with sync_playwright() as p:
            # Stealth args to bypass Cloudflare headless bot detection
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
                viewport={"width": 1280, "height": 720}
            )
            
            # Mask navigator.webdriver
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page.on("response", handle_response)

            print("Navigating to World Rugby fixtures...")
            page.goto("https://www.world.rugby/fixtures", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)  # Allow dynamic scripts time to trigger API calls
            
            # Scroll to trigger lazy-loaded widgets
            page.evaluate("window.scrollBy(0, 500)")
            page.wait_for_timeout(3000)

            browser.close()
    except Exception as e:
        print(f"Browser execution note: {e}")

    print(f"Total raw matches intercepted: {len(captured_matches)}")

    events = []
    seen_matches = set()

    for match in captured_matches:
        teams = match.get("teams", [])
        if not isinstance(teams, list) or len(teams) < 2:
            continue

        t1_name = teams[0].get("name", "") if isinstance(teams[0], dict) else ""
        t2_name = teams[1].get("name", "") if isinstance(teams[1], dict) else ""
        t1_abbr = teams[0].get("abbreviation", "") if isinstance(teams[0], dict) else ""
        t2_abbr = teams[1].get("abbreviation", "") if isinstance(teams[1], dict) else ""

        search_str = f"{t1_name} {t2_name} {t1_abbr} {t2_abbr}"
        if any(k in search_str for k in ["South Africa", "Springboks", "RSA"]):
            time_info = match.get("time", {})
            timestamp_ms = time_info.get("millis") if isinstance(time_info, dict) else None
            if not timestamp_ms:
                continue

            start_dt_utc = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
            match_key = f"{t1_name}-{t2_name}-{start_dt_utc.timestamp()}"

            if match_key in seen_matches:
                continue
            seen_matches.add(match_key)

            end_dt_utc = start_dt_utc + timedelta(hours=2)
            sast_dt = start_dt_utc.astimezone(ZoneInfo("Africa/Johannesburg"))

            summary = f"{format_team(t1_name)} vs {format_team(t2_name)}"
            match_id = match.get("matchId", f"{start_dt_utc.timestamp()}")

            events.append(create_ics_event(summary, start_dt_utc, end_dt_utc, match_id))
            print(f"Added match: {summary} on {sast_dt.strftime('%Y-%m-%d %H:%M SAST')}")

    print(f"Total Springboks events compiled: {len(events)}")

    if not events:
        print("ERROR: No Springboks events compiled. Aborting calendar update.")
        sys.exit(1)

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Springboks Fixtures//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Springboks Rugby",
        *events,
        "END:VCALENDAR"
    ]

    with open("springboks.ics", "w", encoding="utf-8") as f:
        f.write("\n".join(ics_content))

    print("File springboks.ics successfully updated.")

if __name__ == "__main__":
    main()
