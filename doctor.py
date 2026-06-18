from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


REQUIRED_FILES = {
    "GOOGLE_CALENDAR_CREDENTIALS_FILE": "Google OAuth client file for Calendar sync",
}

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
    if provider not in REQUIRED_BY_PROVIDER:
        failures.append("NOTIFIER_PROVIDER must be one of: twilio, macos, console")
    else:
        for key in REQUIRED_BY_PROVIDER[provider]:
            if not os.getenv(key):
                failures.append(f"Missing {key} for {provider} notifications")

    if not os.getenv("OPENAI_API_KEY"):
        warnings.append("OPENAI_API_KEY is missing; app will use local fallback notes")

    for key, description in REQUIRED_FILES.items():
        value = os.getenv(key)
        if not value:
            failures.append(f"Missing {key}: {description}")
        elif not Path(value).exists():
            failures.append(f"{key} points to missing file: {value}")

    token_file = Path(os.getenv("GOOGLE_CALENDAR_TOKEN_FILE", "token.json"))
    if not token_file.exists():
        warnings.append("Google token file is not present yet; first calendar fetch will start OAuth")

    print("Calendar Prep Doctor")
    print("====================")
    print(f"Notifier provider: {provider}")
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

