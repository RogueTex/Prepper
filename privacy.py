from __future__ import annotations

import copy
import os
import re
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\w)")
URL_RE = re.compile(r"https?://\S+|www\.\S+")


def privacy_redaction_enabled() -> bool:
    return os.getenv("REDACT_PRIVATE_DETAILS", "true").strip().lower() not in {"0", "false", "no"}


def sanitize_text(value: Any) -> str:
    text = str(value or "")
    if not privacy_redaction_enabled():
        return text
    text = URL_RE.sub("[link]", text)
    text = EMAIL_RE.sub(lambda match: f"[email at {match.group(1).lower()}]", text)
    text = PHONE_RE.sub("[phone]", text)
    return text


def sanitize_event_for_model(event: dict[str, Any]) -> dict[str, Any]:
    if not privacy_redaction_enabled():
        return copy.deepcopy(event)

    sanitized: dict[str, Any] = {}
    for key, value in event.items():
        if key == "attendees" and isinstance(value, list):
            sanitized[key] = [_sanitize_attendee(attendee) for attendee in value]
        elif isinstance(value, str):
            sanitized[key] = sanitize_text(value)
        elif isinstance(value, list):
            sanitized[key] = [sanitize_text(item) if isinstance(item, str) else item for item in value]
        else:
            sanitized[key] = copy.deepcopy(value)
    return sanitized


def attendee_email_domain(attendee: dict[str, Any]) -> str:
    email = str(attendee.get("email") or "")
    match = EMAIL_RE.search(email)
    return match.group(1).lower() if match else ""


def _sanitize_attendee(attendee: Any) -> Any:
    if not isinstance(attendee, dict):
        return sanitize_text(attendee)

    sanitized = {
        key: sanitize_text(value) if isinstance(value, str) else copy.deepcopy(value)
        for key, value in attendee.items()
        if key != "email"
    }
    domain = attendee_email_domain(attendee)
    if domain:
        sanitized["email_domain"] = domain
    return sanitized
