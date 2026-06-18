from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import requests


class NotificationError(RuntimeError):
    pass


def send_sms(body: str, to_number: str | None = None) -> dict[str, Any]:
    provider = os.getenv("NOTIFIER_PROVIDER", "console").strip().lower()
    if provider == "console":
        return _send_console(body, to_number=to_number)
    if provider == "macos":
        return _send_macos_messages(body, to_number=to_number)
    if provider == "twilio":
        return _send_twilio(body, to_number=to_number)
    raise NotificationError("NOTIFIER_PROVIDER must be one of: twilio, macos, console")


def _send_twilio(body: str, to_number: str | None = None) -> dict[str, Any]:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    target = to_number or os.getenv("PREP_TO_NUMBER")

    missing = [
        name
        for name, value in {
            "TWILIO_ACCOUNT_SID": account_sid,
            "TWILIO_AUTH_TOKEN": auth_token,
            "TWILIO_FROM_NUMBER": from_number,
            "PREP_TO_NUMBER": target,
        }.items()
        if not value
    ]
    if missing:
        raise NotificationError(f"Missing SMS config: {', '.join(missing)}")

    response = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        data={
            "From": from_number,
            "To": target,
            "Body": _sms_compact(body),
        },
        auth=(account_sid, auth_token),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _send_macos_messages(body: str, to_number: str | None = None) -> dict[str, Any]:
    target = to_number or os.getenv("PREP_TO_NUMBER")
    if not target:
        raise NotificationError("Missing SMS config: PREP_TO_NUMBER")

    script = """
    on run argv
      set targetBuddy to item 1 of argv
      set messageText to item 2 of argv
      tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetContact to buddy targetBuddy of targetService
        send messageText to targetContact
      end tell
    end run
    """
    result = subprocess.run(
        ["osascript", "-e", script, target, _sms_compact(body)],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "osascript failed"
        raise NotificationError(detail)
    return {"sid": "macos-messages", "status": "queued", "to": target}


def _send_console(body: str, to_number: str | None = None) -> dict[str, Any]:
    target = to_number or os.getenv("PREP_TO_NUMBER") or "console"
    outbox = Path("outbox")
    outbox.mkdir(exist_ok=True)
    path = outbox / "latest_sms.txt"
    path.write_text(_sms_compact(body), encoding="utf-8")
    return {"sid": str(path), "status": "written", "to": target}


def _sms_compact(body: str, limit: int = 1400) -> str:
    text = "\n".join(line.rstrip() for line in body.strip().splitlines() if line.strip())
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n...[truncated]"
