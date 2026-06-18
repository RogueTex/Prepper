from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def list_upcoming_events(
    max_results: int = 5,
    calendar_id: str | None = None,
    lookahead_minutes: int | None = None,
) -> list[dict[str, Any]]:
    source = os.getenv("CALENDAR_SOURCE", "google_api").strip().lower()
    if source == "google_api":
        return _list_google_api_events(
            max_results=max_results,
            calendar_id=calendar_id,
            lookahead_minutes=lookahead_minutes,
        )
    if source == "ical":
        return _list_ical_events(max_results=max_results, lookahead_minutes=lookahead_minutes)
    if source == "macos":
        return _list_macos_calendar_events(max_results=max_results, lookahead_minutes=lookahead_minutes)
    if source == "sample":
        return _list_sample_events(max_results=max_results, lookahead_minutes=lookahead_minutes)
    raise ValueError("CALENDAR_SOURCE must be one of: google_api, ical, macos, sample")


def _list_google_api_events(
    max_results: int = 5,
    calendar_id: str | None = None,
    lookahead_minutes: int | None = None,
) -> list[dict[str, Any]]:
    service = _calendar_service()
    now = dt.datetime.now(dt.timezone.utc)
    params: dict[str, Any] = {
        "calendarId": calendar_id or os.getenv("GOOGLE_CALENDAR_ID", "primary"),
        "timeMin": now.isoformat(),
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if lookahead_minutes:
        params["timeMax"] = (now + dt.timedelta(minutes=lookahead_minutes)).isoformat()

    result = service.events().list(**params).execute()
    return [_normalize_event(event) for event in result.get("items", [])]


def _list_ical_events(max_results: int = 5, lookahead_minutes: int | None = None) -> list[dict[str, Any]]:
    ical_url = os.getenv("GOOGLE_CALENDAR_ICAL_URL")
    ical_file = os.getenv("GOOGLE_CALENDAR_ICAL_FILE")
    if ical_url:
        response = requests.get(ical_url, timeout=15)
        response.raise_for_status()
        ical_text = response.text
    elif ical_file:
        ical_text = Path(ical_file).read_text(encoding="utf-8")
    else:
        raise FileNotFoundError("Set GOOGLE_CALENDAR_ICAL_URL or GOOGLE_CALENDAR_ICAL_FILE for CALENDAR_SOURCE=ical")

    return _filter_upcoming(_parse_ics_events(ical_text), max_results=max_results, lookahead_minutes=lookahead_minutes)


def _list_sample_events(max_results: int = 5, lookahead_minutes: int | None = None) -> list[dict[str, Any]]:
    ical_text = Path("sample_calendar.ics").read_text(encoding="utf-8")
    return _filter_upcoming(_parse_ics_events(ical_text), max_results=max_results, lookahead_minutes=lookahead_minutes)


def _list_macos_calendar_events(max_results: int = 5, lookahead_minutes: int | None = None) -> list[dict[str, Any]]:
    minutes = lookahead_minutes or 24 * 60
    script = """
    on run argv
      set maxCount to item 1 of argv as integer
      set lookaheadMinutes to item 2 of argv as integer
      set nowDate to current date
      set endDate to nowDate + (lookaheadMinutes * minutes)
      set rows to {}
      tell application "Calendar"
        repeat with cal in calendars
          set eventList to (every event of cal whose start date is greater than or equal to nowDate and start date is less than or equal to endDate)
          repeat with ev in eventList
            set rowText to uid of ev & tab & summary of ev & tab & (start date of ev as «class isot» as string) & tab & (end date of ev as «class isot» as string) & tab & description of ev & tab & location of ev
            copy rowText to end of rows
            if (count of rows) is greater than or equal to maxCount then return rows as string
          end repeat
        end repeat
      end tell
      return rows as string
    end run
    """
    result = subprocess.run(
        ["osascript", "-e", script, str(max_results), str(minutes)],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "osascript Calendar query failed"
        raise RuntimeError(detail)
    events = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        events.append(
            {
                "id": parts[0],
                "title": parts[1] or "Untitled meeting",
                "start": parts[2],
                "end": parts[3],
                "attendees": [],
                "description": parts[4],
                "location": parts[5],
                "html_link": "",
            }
        )
    return events[:max_results]


def _calendar_service():
    credentials = _load_credentials()
    return build("calendar", "v3", credentials=credentials)


def _load_credentials() -> Credentials:
    token_file = Path(os.getenv("GOOGLE_CALENDAR_TOKEN_FILE", "token.json"))
    credentials_file = Path(os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE", "credentials.json"))

    credentials = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        if not credentials_file.exists():
            raise FileNotFoundError(
                f"Missing Google OAuth client file: {credentials_file}. "
                "Set GOOGLE_CALENDAR_CREDENTIALS_FILE in .env."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
        credentials = flow.run_local_server(port=int(os.getenv("GOOGLE_OAUTH_PORT", "0")))
        token_file.write_text(credentials.to_json(), encoding="utf-8")

    return credentials


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event.get("id") or "",
        "title": event.get("summary") or "Untitled meeting",
        "start": start.get("dateTime") or start.get("date") or "",
        "end": end.get("dateTime") or end.get("date") or "",
        "attendees": [_normalize_attendee(attendee) for attendee in event.get("attendees", [])],
        "description": event.get("description") or "",
        "location": event.get("location") or "",
        "html_link": event.get("htmlLink") or "",
    }


def _normalize_attendee(attendee: dict[str, Any]) -> dict[str, str]:
    return {
        "name": attendee.get("displayName") or "",
        "email": attendee.get("email") or "",
        "response_status": attendee.get("responseStatus") or "",
    }


def _parse_ics_events(ical_text: str) -> list[dict[str, Any]]:
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", _unfold_ics(ical_text), flags=re.S):
        fields = _parse_ics_fields(block)
        uid = fields.get("UID", [""])[0]
        attendees = [_parse_ics_attendee(raw) for raw in fields.get("ATTENDEE", [])]
        events.append(
            {
                "id": uid,
                "title": fields.get("SUMMARY", ["Untitled meeting"])[0],
                "start": _parse_ics_datetime(fields.get("DTSTART", [""])[0]),
                "end": _parse_ics_datetime(fields.get("DTEND", [""])[0]),
                "attendees": attendees,
                "description": fields.get("DESCRIPTION", [""])[0],
                "location": fields.get("LOCATION", [""])[0],
                "html_link": "",
            }
        )
    return events


def _unfold_ics(ical_text: str) -> str:
    return re.sub(r"\r?\n[ \t]", "", ical_text)


def _parse_ics_fields(block: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for raw_line in block.splitlines():
        if ":" not in raw_line:
            continue
        left, value = raw_line.split(":", 1)
        key = left.split(";", 1)[0].upper()
        fields.setdefault(key, []).append(_unescape_ics(value.strip()))
    return fields


def _parse_ics_attendee(raw: str) -> dict[str, str]:
    email = raw.replace("mailto:", "").strip()
    return {"name": "", "email": email, "response_status": ""}


def _parse_ics_datetime(value: str) -> str:
    if not value:
        return ""
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            parsed = dt.datetime.strptime(value, fmt)
            if value.endswith("Z"):
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.isoformat()
        except ValueError:
            continue
    return value


def _filter_upcoming(
    events: list[dict[str, Any]],
    max_results: int,
    lookahead_minutes: int | None = None,
) -> list[dict[str, Any]]:
    now = dt.datetime.now(dt.timezone.utc)
    until = now + dt.timedelta(minutes=lookahead_minutes) if lookahead_minutes else None

    def event_start(event: dict[str, Any]) -> dt.datetime:
        parsed = _coerce_datetime(event.get("start") or "")
        return parsed or dt.datetime.max.replace(tzinfo=dt.timezone.utc)

    upcoming = []
    for event in events:
        start = event_start(event)
        if start < now:
            continue
        if until and start > until:
            continue
        upcoming.append(event)
    return sorted(upcoming, key=event_start)[:max_results]


def _coerce_datetime(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return parsed.astimezone(dt.timezone.utc)


def _unescape_ics(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )
