import sys
import os
import re
import uuid
import hashlib
import traceback
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
import urllib.parse

# Optional dependencies for more robust parsing and fetching
try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    requests = None
    BeautifulSoup = None

# date parsing
try:
    from dateutil import parser as dateparser
except Exception:
    dateparser = None

# Playwright is optional fallback for JS-rendered pages
try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

# Prefer icalendar if available for RFC-compliant ICS
try:
    from icalendar import Calendar, Event, vCalAddress, vText
    ICAL_AVAILABLE = True
except Exception:
    ICAL_AVAILABLE = False

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}

# Keywords to ignore (women / junior / sevens)
IGNORE_KEYWORDS = [r"WOMEN", r"U[- ]?20", r"U[- ]?21", r"U[- ]?18", r"SEVEN", r"7S", r"SEVENS", r"UNDER \d+"]

SNAPSHOT_DIR = "snapshots"


def ensure_snapshot_dir():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def snapshot_filename(url, suffix):
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.replace(':', '_')
    path = parsed.path.strip('/').replace('/', '_') or 'root'
    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    safe = f"{host}__{path}__{ts}.{suffix}"
    return os.path.join(SNAPSHOT_DIR, safe)


def save_snapshot(url, html, body_text=None):
    ensure_snapshot_dir()
    html_path = snapshot_filename(url, 'html')
    try:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"Saved snapshot HTML: {html_path}")
    except Exception as e:
        print(f"Failed to save HTML snapshot: {e}")

    if body_text is not None:
        body_path = snapshot_filename(url, 'body.txt')
        try:
            with open(body_path, 'w', encoding='utf-8') as f:
                f.write(body_text)
            print(f"Saved snapshot BODY text: {body_path}")
        except Exception as e:
            print(f"Failed to save BODY snapshot: {e}")


def format_team(name):
    if not name:
        return name
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
        return "🏴 England"
    elif "WALES" in upper:
        return "🏴 Wales"
    elif "SCOTLAND" in upper:
        return "🏴 Scotland"
    elif "JAPAN" in upper:
        return "🇯🇵 Japan"
    elif "FIJI" in upper:
        return "🇫🇯 Fiji"
    return f"🏉 {name.strip().title()}"


def stable_uid(team_home, team_away, year, month, day):
    """Create a deterministic UID based on the teams and date only (stable across time changes).
    """
    base = f"{team_home.strip().lower()}|{team_away.strip().lower()}|{year:04d}-{month:02d}-{day:02d}"
    h = hashlib.sha1(base.encode('utf-8')).hexdigest()
    return f"{h}@sarugby"


def escape_ics_text(text: str) -> str:
    if not text:
        return ""
    # Escape backslashes first
    text = text.replace('\\', '\\\\')
    text = text.replace('\n', '\\n')
    text = text.replace('\r', '')
    text = text.replace(',', '\\,')
    text = text.replace(';', '\\;')
    return text


def parse_time_from_line(line, year, month, day, sast_tz):
    """Try to parse a time expression from a line.
    Returns (hour, minute) or None if not found or TBC.
    Uses dateutil if available, otherwise falls back to simple HH:MM match.
    """
    if not line:
        return None
    line = line.strip()
    if line.upper().startswith("TBC") or "TBC" in line.upper() or "TBA" in line.upper():
        return None

    # Look for HH:MM with optional AM/PM and optional timezone
    time_re = re.search(r"(\d{1,2}:\d{2})(?:\s*([APap][Mm]))?", line)
    if time_re:
        try:
            if dateparser:
                dt = dateparser.parse(f"{day} {month} {year} {time_re.group(0)}")
                return dt.hour, dt.minute
            else:
                h, m = time_re.group(1).split(":")
                hh = int(h)
                mm = int(m)
                ampm = time_re.group(2)
                if ampm:
                    if ampm.lower() == 'pm' and hh != 12:
                        hh += 12
                    if ampm.lower() == 'am' and hh == 12:
                        hh = 0
                return hh, mm
        except Exception:
            return None
    return None


def parse_springboks_fixtures(page_text, source_url=None):
    events = []
    seen = set()
    try:
        sast_tz = ZoneInfo("Africa/Johannesburg")
    except Exception:
        sast_tz = timezone(timedelta(hours=2))  # fallback to UTC+2

    # Normalize text and split
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]

    # Save a small debug dump of the normalized body for inspection
    try:
        ensure_snapshot_dir()
        dbg_path = os.path.join(SNAPSHOT_DIR, f"body_debug_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.txt")
        with open(dbg_path, 'w', encoding='utf-8') as dbg_f:
            dbg_f.write('\n'.join(lines[:400]))
        print(f"Saved parser debug body excerpt: {dbg_path}")
    except Exception:
        pass

    current_year = datetime.now().year
    current_month = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect Month/Year headers (e.g. "AUGUST 2026")
        header_m = re.search(r'^(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{4})$', line, re.IGNORECASE)
        if header_m:
            current_month = MONTH_MAP[header_m.group(1).lower()]
            current_year = int(header_m.group(2))
            i += 1
            continue

        # Detect Date headers with optional month (e.g. "Sat 29 Aug", "29 Aug", "29")
        date_m = re.search(r'^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*(\d{1,2})(?:\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December))?$', line, re.IGNORECASE)
        if date_m:
            day = int(date_m.group(1))
            month_group = date_m.group(2)
            if month_group:
                month = MONTH_MAP[month_group.lower()]
            else:
                month = current_month or datetime.now().month
            year = current_year or datetime.now().year

            # Look ahead block for details
            block = lines[i+1 : i+20]
            team_home, team_away = None, None
            venue, tournament = "", ""
            time_tuple = None

            for b_idx, b_line in enumerate(block):
                # Try parse time
                if not time_tuple:
                    t = parse_time_from_line(b_line, year, month, day, sast_tz)
                    if t:
                        time_tuple = t

                # Teams: handle many variants of separators
                vs_m = re.search(r'^(.+?)\s+(?:v|vs|v\.|vs\.|–|—|-|\u2013|\u2014)\s+(.+?)$', b_line, re.IGNORECASE)
                if vs_m:
                    team_home = vs_m.group(1).strip()
                    team_away = vs_m.group(2).strip()
                elif b_line.upper() in ["V", "VS"] and b_idx > 0 and b_idx + 1 < len(block):
                    team_home = block[b_idx - 1].strip()
                    team_away = block[b_idx + 1].strip()

                # Venue detection (loose)
                up = b_line.upper()
                if any(k in up for k in ["STADIUM", "PARK", "ARENA", "FIELD", "GROUND"]):
                    venue = b_line.strip()
                # Tournament keywords
                if any(k in up for k in ["RIVALRY", "CHAMPIONSHIP", "TEST", "INTERNATIONAL", "SERIES", "TOURNAMENT"]):
                    tournament = b_line.strip()

            # Validate teams and filter out non-senior matches
            if team_home and team_away:
                combined = f"{team_home} {team_away}".upper()
                if ("SPRINGBOK" in combined or "SOUTH AFRICA" in combined) and not any(re.search(pat, combined) for pat in IGNORE_KEYWORDS):
                    # Determine time
                    if time_tuple:
                        hour, minute = time_tuple
                        dt_sast = datetime(year, month, day, hour, minute, tzinfo=sast_tz)
                    else:
                        dt_sast = None

                    key = f"{team_home}-{team_away}-{year}-{month}-{day}"
                    if key not in seen:
                        seen.add(key)

                        # Stable UID based on teams+date only
                        uid = stable_uid(team_home, team_away, year, month, day)

                        # Description
                        desc_parts = []
                        if tournament:
                            desc_parts.append(tournament)
                        if not dt_sast:
                            desc_parts.append("Time: TBC")
                        if source_url:
                            desc_parts.append(f"Source: {source_url}")
                        description = " | ".join(desc_parts)

                        # Build event record depending on whether we have a time
                        if dt_sast:
                            dt_utc = dt_sast.astimezone(timezone.utc)
                            dt_end_utc = dt_utc + timedelta(hours=2)
                            event_record = {
                                'uid': uid,
                                'summary': f"{format_team(team_home)} vs {format_team(team_away)}",
                                'dtstart': dt_utc,
                                'dtend': dt_end_utc,
                                'location': venue,
                                'description': description,
                                'url': source_url
                            }
                        else:
                            # All-day event for TBC
                            event_record = {
                                'uid': uid,
                                'summary': f"{format_team(team_home)} vs {format_team(team_away)}",
                                'dtstart_date': date(year, month, day),
                                'dtend_date': date(year, month, day) + timedelta(days=1),
                                'location': venue,
                                'description': description,
                                'url': source_url
                            }

                        events.append(event_record)
                        if dt_sast:
                            print(f"Added Springboks Test: {event_record['summary']} on {dt_sast.strftime('%Y-%m-%d %H:%M SAST')}")
                        else:
                            print(f"Added Springboks Test (TBC time): {event_record['summary']} on {year}-{month:02d}-{day:02d}")

        i += 1

    return events


def fetch_page_with_requests(url, timeout=15):
    if not requests:
        return None
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200 and r.text and len(r.text) > 200:
            # Save snapshot of raw HTML
            try:
                save_snapshot(url, r.text)
            except Exception:
                pass
            return r.text
    except Exception:
        return None
    return None


def fetch_page_with_playwright(url):
    if not sync_playwright:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", viewport={"width":1280, "height":900})
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page.goto(url, wait_until="networkidle", timeout=30000)
            for _ in range(8):
                try:
                    page.evaluate("window.scrollBy(0, 800)")
                except Exception:
                    pass
                page.wait_for_timeout(400)
            body = page.content()
            # Save snapshot of raw HTML and body text
            try:
                text_body = page.inner_text('body')
            except Exception:
                text_body = None
            try:
                save_snapshot(url, body, body_text=text_body)
            except Exception:
                pass
            browser.close()
            return body
    except Exception:
        return None


def build_ics(events):
    # If icalendar is available, prefer it for richer/valid ICS
    if ICAL_AVAILABLE:
        cal = Calendar()
        cal.add('prodid', '-//Springboks Official Test Fixtures//EN')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('X-WR-CALNAME', 'Springboks Rugby')

        for ev in events:
            e = Event()
            e.add('uid', ev['uid'])
            e.add('summary', ev['summary'])
            e.add('dtstamp', datetime.now(timezone.utc))
            if 'dtstart' in ev:
                e.add('dtstart', ev['dtstart'])
                e.add('dtend', ev['dtend'])
            else:
                # all-day
                e.add('dtstart', ev['dtstart_date'])
                e.add('dtend', ev['dtend_date'])

            if ev.get('location'):
                e.add('location', vText(ev.get('location')))
            if ev.get('description'):
                e.add('description', vText(ev.get('description')))
            if ev.get('url'):
                e.add('url', ev.get('url'))

            # Organizer placeholder (optional)
            try:
                organizer = vCalAddress('MAILTO:info@springboks.rugby')
                organizer.params['cn'] = vText('Springboks')
                e['organizer'] = organizer
            except Exception:
                pass

            cal.add_component(e)

        return cal.to_ical().decode('utf-8')

    # Fallback: manual ICS building (less rich)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Springboks Official Test Fixtures//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Springboks Rugby",
    ]

    for ev in events:
        lines.append('BEGIN:VEVENT')
        lines.append(f"UID:{ev['uid']}")
        lines.append(f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
        if 'dtstart' in ev:
            lines.append(f"DTSTART:{ev['dtstart'].strftime('%Y%m%dT%H%M%SZ')}")
            lines.append(f"DTEND:{ev['dtend'].strftime('%Y%m%dT%H%M%SZ')}")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{ev['dtstart_date'].strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{ev['dtend_date'].strftime('%Y%m%d')}")
        lines.append(f"SUMMARY:{escape_ics_text(ev['summary'])}")
        if ev.get('location'):
            lines.append(f"LOCATION:{escape_ics_text(ev.get('location'))}")
        if ev.get('description'):
            lines.append(f"DESCRIPTION:{escape_ics_text(ev.get('description'))}")
        if ev.get('url'):
            lines.append(f"URL:{ev.get('url')}")
        lines.append('STATUS:CONFIRMED')
        lines.append('END:VEVENT')

    lines.append('END:VCALENDAR')
    return '\n'.join(lines)


def main():
    print("Fetching official Springboks Test fixtures...")
    events = []

    urls = [
        ("https://springboks.rugby/match-centre/fixtures", "https://springboks.rugby/match-centre/fixtures"),
        ("https://www.world.rugby/tournaments/fixtures-results", "https://www.world.rugby/tournaments/fixtures-results")
    ]

    for target_url, source_url in urls:
        print(f"Fetching {target_url}...")
        page_text = fetch_page_with_requests(target_url)
        if not page_text:
            print("Requests fetch failed or returned too little content; trying Playwright (if available)...")
            page_text = fetch_page_with_playwright(target_url)
        if not page_text:
            print(f"Warning: Unable to fetch content from {target_url}")
            continue

        if BeautifulSoup:
            try:
                soup = BeautifulSoup(page_text, "lxml")
                body = soup.get_text(separator="\n")
            except Exception:
                body = page_text
        else:
            body = page_text

        try:
            events.extend(parse_springboks_fixtures(body, source_url=source_url))
        except Exception:
            print("Error parsing page; continuing to next URL")
            traceback.print_exc()

    # Deduplicate by UID to ensure stability
    unique = {}
    for ev in events:
        unique[ev['uid']] = ev

    compiled = list(unique.values())

    print(f"Total official Springboks Test events compiled: {len(compiled)}")

    # If zero events, write a debug index file pointing to any snapshots
    if len(compiled) == 0:
        try:
            ensure_snapshot_dir()
            files = os.listdir(SNAPSHOT_DIR)
            debug_index = os.path.join(SNAPSHOT_DIR, 'debug_index.txt')
            with open(debug_index, 'w', encoding='utf-8') as di:
                di.write('No events parsed. Snapshot files present:\n')
                for fn in files:
                    di.write(fn + '\n')
            print(f"Wrote snapshot index: {debug_index}")
        except Exception:
            pass

    ics_text = build_ics(compiled)

    with open("springboks.ics", "w", encoding="utf-8") as f:
        f.write(ics_text)

    print("File springboks.ics successfully updated with official Senior Test matches.")


if __name__ == "__main__":
    main()
