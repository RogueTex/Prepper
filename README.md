# Calendar Prep Flask

A local Flask microservice that syncs with Google Calendar, does a lightweight attendee/domain lookup, generates quick meeting prep notes with OpenAI, and can send those notes by SMS.

This is designed to run locally. The sample data is synthetic, and private calendar events, OAuth tokens, phone numbers, generated briefs, and API keys should never be committed.

## What It Does

- Connects to Google Calendar with read-only OAuth.
- Fetches upcoming meetings from your calendar.
- Builds lightweight context from event metadata and optional public domain lookup.
- Generates prep notes through the OpenAI Responses API when `OPENAI_API_KEY` is set.
- Falls back to a deterministic local brief when no OpenAI key is configured.
- Sends a selected prep note by SMS through Twilio.
- Supports notification providers: `twilio`, `macos`, and `console`.
- Includes a reminder worker that can poll for upcoming meetings and text prep notes automatically.

## Quick Start

```bash
/Users/raghu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m venv .venv312
source .venv312/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Google Calendar Setup

Create a Google Cloud OAuth client for a desktop app, download the client JSON, and save it locally as:

```text
credentials.json
```

Then set:

```bash
GOOGLE_CALENDAR_CREDENTIALS_FILE=credentials.json
GOOGLE_CALENDAR_TOKEN_FILE=token.json
GOOGLE_CALENDAR_ID=primary
```

The first calendar fetch opens a browser for OAuth consent and stores a local `token.json`. Both files are ignored by git.

## OpenAI Setup

Set:

```bash
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

The app uses the OpenAI Responses API for richer prep notes. Without an API key, the local fallback still works for demos and development.

## SMS Setup

Pick a notifier:

```bash
NOTIFIER_PROVIDER=console
```

Providers:

- `console`: writes the latest "SMS" body to `outbox/latest_sms.txt`; good for dry-runs.
- `twilio`: sends a real SMS through Twilio.
- `macos`: sends through the local macOS Messages app, if Messages and SMS/iMessage routing are configured on your Mac.

For Twilio, set:

```bash
NOTIFIER_PROVIDER=twilio
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+15555550123
PREP_TO_NUMBER=+15555550124
```

For macOS Messages, set:

```bash
NOTIFIER_PROVIDER=macos
PREP_TO_NUMBER=+15555550124
```

Then use the web UI button or:

```bash
curl -X POST http://127.0.0.1:5000/api/sms \
  -H "Content-Type: application/json" \
  -d '{"body":"Prep note test"}'
```

## CLI

Run a local setup check:

```bash
python doctor.py
```

Generate a brief from the synthetic sample:

```bash
python cli.py brief --event-file sample_event.json
```

Write the generated note through the configured notifier:

```bash
python cli.py brief --event-file sample_event.json --sms
```

List upcoming Google Calendar events:

```bash
python cli.py events --max-results 5
```

## API

Fetch upcoming calendar events:

```bash
curl "http://127.0.0.1:5000/api/events?max_results=5"
```

Generate a brief from sample JSON:

```bash
curl -X POST http://127.0.0.1:5000/api/brief \
  -H "Content-Type: application/json" \
  -d @sample_event.json
```

Generate briefs for upcoming events:

```bash
curl -X POST "http://127.0.0.1:5000/api/brief/upcoming?max_results=3"
```

## Reminder Worker

To automatically text prep notes for meetings coming up soon:

```bash
python reminder_worker.py
```

Useful settings:

```bash
DEFAULT_LOOKAHEAD_MINUTES=45
REMINDER_POLL_SECONDS=300
```

The worker tracks sent event IDs in `briefs/sent_reminders.json`, which is ignored by git.

## Optional Lookup

By default, lookup only extracts non-personal attendee domains. To allow a small homepage metadata lookup for those domains:

```bash
ENABLE_DOMAIN_LOOKUP=true
```

The lookup sends only the public domain, not meeting notes or attendee names.

## Privacy Guardrails

- `.env`, `credentials.json`, `token.json`, and generated `briefs/` files are gitignored.
- Public examples use synthetic people, companies, emails, and domains only.
- Domain lookup sends only public domains.
- OpenAI inference receives the event payload you submit. Keep the app local and avoid sending sensitive descriptions or private notes unless you are comfortable using them for inference.
- Do not paste real email threads, calendar invites, or private company names into committed sample files.
