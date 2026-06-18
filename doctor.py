from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


REQUIRED_BY_PROVIDER = {
    "twilio": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER", "PREP_TO_NUMBER"],
    "macos": ["PREP_TO_NUMBER"],
    "console": [],
}


def main() -> None:
    load_dotenv()
    failures: list[str] = []
    warnings: list[str] = []

    provider = os.getenv("NOTIFIER_PROVIDER", "twilio").strip().lower()
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


if __name__ == "__main__":
    main()
