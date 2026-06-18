from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Any

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

