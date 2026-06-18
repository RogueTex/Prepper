from __future__ import annotations

import argparse
import getpass
from collections import OrderedDict
from pathlib import Path


DEFAULTS = OrderedDict(
    [
        ("OPENAI_API_KEY", ""),
        ("OPENAI_MODEL", "gpt-4.1-mini"),
        ("CALENDAR_SOURCE", "macos"),
        ("GOOGLE_CALENDAR_CREDENTIALS_FILE", "credentials.json"),
        ("GOOGLE_CALENDAR_TOKEN_FILE", "token.json"),
        ("GOOGLE_CALENDAR_ID", "primary"),
        ("GOOGLE_CALENDAR_ICAL_URL", ""),
        ("GOOGLE_CALENDAR_ICAL_FILE", ""),
        ("ENABLE_DOMAIN_LOOKUP", "false"),
        ("REDACT_PRIVATE_DETAILS", "true"),
        ("NOTIFIER_PROVIDER", "console"),
        ("TWILIO_ACCOUNT_SID", ""),
        ("TWILIO_AUTH_TOKEN", ""),
        ("TWILIO_FROM_NUMBER", ""),
        ("PREP_TO_NUMBER", ""),
        ("DEFAULT_LOOKAHEAD_MINUTES", "45"),
        ("REMINDER_POLL_SECONDS", "300"),
    ]
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a local Prepper .env file")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--preset",
        choices=["macos-console", "sample-console"],
        help="Write a safe non-interactive local preset.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing env file without prompting.",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file)
    existing = read_env(env_path)
    config = OrderedDict(DEFAULTS)
    config.update({key: value for key, value in existing.items() if key in DEFAULTS})

    if args.preset:
        apply_preset(config, args.preset)
    else:
        configure_interactively(config)

    if env_path.exists() and not args.force and not confirm(f"Overwrite {env_path}?"):
        print("Canceled; no file was changed.")
        return

    write_env(env_path, config)
    print(f"Wrote {env_path}")
    print("Next: python doctor.py --probe")


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def apply_preset(config: OrderedDict[str, str], preset: str) -> None:
    if preset == "macos-console":
        config["CALENDAR_SOURCE"] = "macos"
        config["NOTIFIER_PROVIDER"] = "console"
        return
    if preset == "sample-console":
        config["CALENDAR_SOURCE"] = "sample"
        config["NOTIFIER_PROVIDER"] = "console"
        return
    raise ValueError(f"Unknown preset: {preset}")


def configure_interactively(config: OrderedDict[str, str]) -> None:
    print("Prepper local setup")
    print("===================")
    print("Secrets are written only to .env, which is ignored by git.\n")

    config["CALENDAR_SOURCE"] = choice(
        "Calendar source",
        ["macos", "ical", "google_api", "sample"],
        config["CALENDAR_SOURCE"],
    )
    if config["CALENDAR_SOURCE"] == "ical":
        config["GOOGLE_CALENDAR_ICAL_URL"] = prompt("Google private iCal URL", config["GOOGLE_CALENDAR_ICAL_URL"])
        config["GOOGLE_CALENDAR_ICAL_FILE"] = prompt(
            "Local iCal file path, optional",
            config["GOOGLE_CALENDAR_ICAL_FILE"],
        )
    elif config["CALENDAR_SOURCE"] == "google_api":
        config["GOOGLE_CALENDAR_CREDENTIALS_FILE"] = prompt(
            "Google OAuth credentials file",
            config["GOOGLE_CALENDAR_CREDENTIALS_FILE"],
        )
        config["GOOGLE_CALENDAR_TOKEN_FILE"] = prompt("Google token file", config["GOOGLE_CALENDAR_TOKEN_FILE"])
        config["GOOGLE_CALENDAR_ID"] = prompt("Google calendar id", config["GOOGLE_CALENDAR_ID"])

    config["OPENAI_MODEL"] = prompt("OpenAI model", config["OPENAI_MODEL"])
    if confirm("Set or replace OPENAI_API_KEY now?", default=False):
        config["OPENAI_API_KEY"] = getpass.getpass("OPENAI_API_KEY: ").strip()

    config["NOTIFIER_PROVIDER"] = choice(
        "Notification provider",
        ["console", "macos", "twilio"],
        config["NOTIFIER_PROVIDER"],
    )
    if config["NOTIFIER_PROVIDER"] == "macos":
        config["PREP_TO_NUMBER"] = prompt("SMS/iMessage destination", config["PREP_TO_NUMBER"])
    elif config["NOTIFIER_PROVIDER"] == "twilio":
        config["TWILIO_ACCOUNT_SID"] = prompt("TWILIO_ACCOUNT_SID", config["TWILIO_ACCOUNT_SID"])
        if confirm("Set or replace TWILIO_AUTH_TOKEN now?", default=False):
            config["TWILIO_AUTH_TOKEN"] = getpass.getpass("TWILIO_AUTH_TOKEN: ").strip()
        config["TWILIO_FROM_NUMBER"] = prompt("TWILIO_FROM_NUMBER", config["TWILIO_FROM_NUMBER"])
        config["PREP_TO_NUMBER"] = prompt("PREP_TO_NUMBER", config["PREP_TO_NUMBER"])

    config["REDACT_PRIVATE_DETAILS"] = "true" if confirm("Redact links, phone numbers, and emails?", True) else "false"


def write_env(path: Path, config: OrderedDict[str, str]) -> None:
    path.write_text("".join(f"{key}={value}\n" for key, value in config.items()), encoding="utf-8")


def choice(label: str, options: list[str], default: str) -> str:
    options_text = "/".join(options)
    while True:
        value = prompt(f"{label} ({options_text})", default).strip().lower()
        if value in options:
            return value
        print(f"Choose one of: {options_text}")


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def confirm(label: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{label} ({suffix}): ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


if __name__ == "__main__":
    main()
