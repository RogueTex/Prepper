from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from calendar_client import list_upcoming_events
from notifier import send_sms
from prep_brief import generate_brief


REQUIRED_BY_PROVIDER = {
    "twilio": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER", "PREP_TO_NUMBER"],
    "macos": ["PREP_TO_NUMBER"],
    "console": [],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local Prepper configuration")
    parser.add_argument("--probe", action="store_true", help="Run a safe calendar, brief, and notifier probe")
    parser.add_argument(
        "--send-test-notification",
        action="store_true",
        help="Actually send through twilio/macos providers during --probe. Console always writes locally.",
    )
    args = parser.parse_args()

    load_dotenv()
    failures: list[str] = []
    warnings: list[str] = []

    provider = os.getenv("NOTIFIER_PROVIDER", "console").strip().lower()
    calendar_source = os.getenv("CALENDAR_SOURCE", "google_api").strip().lower()
    if provider not in REQUIRED_BY_PROVIDER:
        failures.append("NOTIFIER_PROVIDER must be one of: twilio, macos, console")
    else:
        for key in REQUIRED_BY_PROVIDER[provider]:
            if not os.getenv(key):
                failures.append(f"Missing {key} for {provider} notifications")

    if not os.getenv("OPENAI_API_KEY"):
        warnings.append("OPENAI_API_KEY is missing; app will use local fallback notes")

    if calendar_source == "google_api":
        credentials_file = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_FILE")
        if not credentials_file:
            failures.append("Missing GOOGLE_CALENDAR_CREDENTIALS_FILE for CALENDAR_SOURCE=google_api")
        elif not Path(credentials_file).exists():
            failures.append(f"GOOGLE_CALENDAR_CREDENTIALS_FILE points to missing file: {credentials_file}")

        token_file = Path(os.getenv("GOOGLE_CALENDAR_TOKEN_FILE", "token.json"))
        if not token_file.exists():
            warnings.append("Google token file is not present yet; first calendar fetch will start OAuth")
    elif calendar_source == "ical":
        ical_url = os.getenv("GOOGLE_CALENDAR_ICAL_URL")
        ical_file = os.getenv("GOOGLE_CALENDAR_ICAL_FILE")
        if not ical_url and not ical_file:
            failures.append("Set GOOGLE_CALENDAR_ICAL_URL or GOOGLE_CALENDAR_ICAL_FILE for CALENDAR_SOURCE=ical")
        if ical_file and not Path(ical_file).exists():
            failures.append(f"GOOGLE_CALENDAR_ICAL_FILE points to missing file: {ical_file}")
    elif calendar_source == "macos":
        warnings.append("macOS Calendar source requires Calendar app access permission on first run")
    elif calendar_source == "sample":
        warnings.append("CALENDAR_SOURCE=sample uses synthetic sample_calendar.ics only")
    else:
        failures.append("CALENDAR_SOURCE must be one of: google_api, ical, macos, sample")

    print("Prepper Doctor")
    print("==============")
    print(f"Notifier provider: {provider}")
    print(f"Calendar source: {calendar_source}")
    print(f"Calendar ID: {os.getenv('GOOGLE_CALENDAR_ID', 'primary')}")
    print(f"OpenAI model: {os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')}")

    if warnings:
        print("\nWarnings")
        for warning in warnings:
            print(f"- {warning}")

    if failures:
        print("\nSetup needed")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("\nReady: required local configuration is present.")
    if args.probe:
        run_probe(send_test_notification=args.send_test_notification)


def run_probe(send_test_notification: bool = False) -> None:
    print("\nProbe")
    print("-----")

    events = list_upcoming_events(max_results=1)
    print(
        json.dumps(
            {
                "calendar_events_seen": len(events),
                "event_has_title": bool(events and events[0].get("title")),
                "event_has_start": bool(events and events[0].get("start")),
            },
            indent=2,
        )
    )
    if not events:
        print(json.dumps({"end_to_end": "skipped", "reason": "No upcoming events found."}, indent=2))
        return

    brief, source = generate_brief(events[0])
    print(
        json.dumps(
            {
                "end_to_end": "calendar_to_brief",
                "brief_source": source,
                "brief_chars": len(brief),
            },
            indent=2,
        )
    )

    provider = os.getenv("NOTIFIER_PROVIDER", "console").strip().lower()
    if provider == "console" or send_test_notification:
        result = send_sms(f"Prepper setup probe\n\nPrep notes ({source})\n\n{brief}")
        print(
            json.dumps(
                {
                    "end_to_end": "calendar_to_brief_to_notification",
                    "notification_status": result.get("status"),
                    "notification_to": result.get("to"),
                },
                indent=2,
            )
        )
    else:
        print(
            json.dumps(
                {
                    "notification_status": "not_sent",
                    "reason": "Use --send-test-notification to send through twilio/macos.",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
