from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from calendar_client import list_upcoming_events
from notifier import send_sms
from prep_brief import generate_brief


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Calendar prep notes CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    events_parser = subparsers.add_parser("events", help="List upcoming calendar events")
    events_parser.add_argument("--max-results", type=int, default=5)

    brief_parser = subparsers.add_parser("brief", help="Generate a brief from an event JSON file")
    brief_parser.add_argument("--event-file", default="sample_event.json")
    brief_parser.add_argument("--sms", action="store_true")
    brief_parser.add_argument("--to")

    upcoming_parser = subparsers.add_parser("brief-upcoming", help="Generate briefs for upcoming events")
    upcoming_parser.add_argument("--max-results", type=int, default=3)
    upcoming_parser.add_argument("--sms", action="store_true")
    upcoming_parser.add_argument("--to")

    args = parser.parse_args()
    if args.command == "events":
        print(json.dumps(list_upcoming_events(max_results=args.max_results), indent=2))
        return

    if args.command == "brief":
        event = json.loads(Path(args.event_file).read_text(encoding="utf-8"))
        brief, source = generate_brief(event)
        print(f"Source: {source}\n\n{brief}")
        if args.sms:
            print(json.dumps(send_sms(f"Prep notes ({source})\n\n{brief}", to_number=args.to), indent=2))
        return

    if args.command == "brief-upcoming":
        events = list_upcoming_events(max_results=args.max_results)
        for index, event in enumerate(events, start=1):
            brief, source = generate_brief(event)
            body = f"#{index}: {event.get('title')}\nPrep notes ({source})\n\n{brief}"
            print(body)
            print("\n---\n")
            if args.sms:
                print(json.dumps(send_sms(body, to_number=args.to), indent=2))


if __name__ == "__main__":
    main()

