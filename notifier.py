from __future__ import annotations

import os
from typing import Any

import requests


class NotificationError(RuntimeError):
    pass


def send_sms(body: str, to_number: str | None = None) -> dict[str, Any]:
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


def _sms_compact(body: str, limit: int = 1400) -> str:
    text = "\n".join(line.rstrip() for line in body.strip().splitlines() if line.strip())
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n...[truncated]"

