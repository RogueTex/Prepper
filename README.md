# Calendar Prep Flask

A small local Flask microservice that turns upcoming calendar events into quick meeting prep briefs.

It is intentionally simple: give it event metadata such as title, attendees, description, and start time, and it returns a concise brief with likely context, reminders, and useful questions to ask. I built this as a personal productivity tool so I can walk into calls with context instead of scrambling five minutes before.

## What It Does

- Accepts meeting details through a JSON API.
- Produces a short prep brief for each meeting.
- Uses an OpenAI-compatible chat completion API when `OPENAI_API_KEY` is available.
- Falls back to a deterministic local summarizer when no API key is configured.
- Includes sample data so the service can be tried without wiring a real calendar.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

Generate a prep brief from the sample event:

```bash
curl -X POST http://127.0.0.1:5000/api/brief \
  -H "Content-Type: application/json" \
  -d @sample_event.json
```

## Optional LLM Mode

Create a `.env` file:

```bash
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

The app will use the LLM for richer briefs. Without an API key, it still works locally with the fallback generator.

## API

`POST /api/brief`

```json
{
  "title": "Intro call with Harper",
  "start": "2026-06-18T14:00:00-07:00",
  "attendees": [
    {
      "name": "Dakotah Rice",
      "email": "dr@example.com",
      "company": "Harper",
      "role": "Founder & CEO"
    }
  ],
  "description": "First conversation for an FDE role.",
  "prior_context": [
    "Applied for Forward Deployed Engineer role.",
    "Harper is building an AI-native commercial insurance brokerage."
  ]
}
```

Response:

```json
{
  "brief": "...",
  "source": "local-fallback"
}
```

## Why This Exists

The goal is not to replace a calendar. It is a tiny workflow tool that sits right before a meeting and answers:

- Who am I meeting?
- What is this probably about?
- What context should I remember?
- What are a few good questions to ask?

