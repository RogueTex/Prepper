from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()


def generate_brief(event: dict[str, Any]) -> tuple[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            return _generate_with_openai(event, api_key), "openai"
        except requests.RequestException:
            pass

    return _generate_locally(event), "local-fallback"


def _generate_with_openai(event: dict[str, Any], api_key: str) -> str:
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = (
        "Create a concise meeting prep brief from this calendar event. "
        "Use short sections: Context, Remember, Questions. "
        "Be practical and avoid making up facts.\n\n"
        f"Event:\n{event}"
    )
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You write crisp, useful meeting prep notes.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def _generate_locally(event: dict[str, Any]) -> str:
    title = event.get("title") or "Untitled meeting"
    start = event.get("start") or "Time not provided"
    description = event.get("description") or "No description provided."
    attendees = event.get("attendees") or []
    prior_context = event.get("prior_context") or []

    attendee_lines = []
    for attendee in attendees:
        if isinstance(attendee, dict):
            name = attendee.get("name") or attendee.get("email") or "Unknown attendee"
            role = attendee.get("role")
            company = attendee.get("company")
            details = ", ".join(part for part in [role, company] if part)
            attendee_lines.append(f"- {name}" + (f" ({details})" if details else ""))
        else:
            attendee_lines.append(f"- {attendee}")

    context_lines = "\n".join(f"- {item}" for item in prior_context) or "- No prior context provided."
    attendee_text = "\n".join(attendee_lines) or "- No attendees provided."

    return f"""Meeting: {title}
Start: {start}

Who is joining:
{attendee_text}

Likely context:
- {description}
{context_lines}

Remember:
- Confirm the other person's goal for the call early.
- Tie your answers to concrete shipped work, not abstract interest.
- Leave with a clear next step.

Questions to ask:
- What workflow is most painful or manual for the team right now?
- Where do AI systems already work well at the company, and where do they still fail?
- What would make someone successful in this role in the first 30 to 60 days?
"""

