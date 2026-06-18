from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from calendar_client import list_upcoming_events
from notifier import send_sms
from prep_brief import generate_brief


load_dotenv()


STATE_FILE = Path("briefs/sent_reminders.json")


def run_loop() -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    sent = _load_sent()
    poll_seconds = int(os.getenv("REMINDER_POLL_SECONDS", "300"))
    lookahead_minutes = int(os.getenv("DEFAULT_LOOKAHEAD_MINUTES", "45"))

    while True:
        sent = send_due_reminders(sent, lookahead_minutes=lookahead_minutes)
        _save_sent(sent)
        time.sleep(poll_seconds)


def send_due_reminders(
    sent: set[str] | None = None,
    lookahead_minutes: int | None = None,
    max_results: int = 10,
) -> set[str]:
    sent = sent or set()
    events = list_upcoming_events(
        max_results=max_results,
        lookahead_minutes=lookahead_minutes or int(os.getenv("DEFAULT_LOOKAHEAD_MINUTES", "45")),
    )
    for event in events:
        event_key = event.get("id") or f"{event.get('title')}:{event.get('start')}"
        if event_key in sent:
            continue

        brief, source = generate_brief(event)
        send_sms(f"Prep notes ({source})\n\n{brief}")
        sent.add(event_key)
    return sent


def run_once(lookahead_minutes: int | None = None, max_results: int = 10) -> int:
    STATE_FILE.parent.mkdir(exist_ok=True)
    before = _load_sent()
    after = send_due_reminders(before, lookahead_minutes=lookahead_minutes, max_results=max_results)
    _save_sent(after)
    sent_count = len(after - before)
    print(json.dumps({"reminders_sent": sent_count, "tracked_events": len(after)}, indent=2))
    return sent_count


def _load_sent() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))


def _save_sent(sent: set[str]) -> None:
    STATE_FILE.write_text(json.dumps(sorted(sent), indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll calendar events and send prep reminders")
    parser.add_argument("--once", action="store_true", help="Run one reminder pass and exit")
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--lookahead-minutes", type=int)
    args = parser.parse_args()

    if args.once:
        run_once(lookahead_minutes=args.lookahead_minutes, max_results=args.max_results)
        return

    run_loop()


if __name__ == "__main__":
    main()
