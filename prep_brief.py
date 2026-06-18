from __future__ import annotations

import os
import json
from typing import Any

import requests
from dotenv import load_dotenv

from lookup import enrich_event
from privacy import attendee_email_domain, sanitize_event_for_model, sanitize_text


load_dotenv()


def generate_brief(event: dict[str, Any]) -> tuple[str, str]:
    lookup_context = enrich_event(event)
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            return _generate_with_openai(event, lookup_context, api_key), "openai"
        except requests.RequestException as exc:
            return _generate_locally(
                event,
                lookup_context,
                error=f"OpenAI request failed: {exc}",
            ), "local-fallback-after-openai-error"

    return _generate_locally(event, lookup_context), "local-fallback"


def _generate_with_openai(event: dict[str, Any], lookup_context: dict[str, Any], api_key: str) -> str:
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    payload = {"event": sanitize_event_for_model(event), "lookup_context": lookup_context}
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You write concise meeting prep notes for one person. "
                        "Use only the supplied calendar event and lookup context. "
                        "Do not invent private facts. If a detail is uncertain, say what to verify."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Create a prep note with these sections: Context, Remember, Questions. "
                        "Keep it under 220 words and make it useful five minutes before a meeting.\n\n"
                        + json.dumps(payload, indent=2)
                    ),
                },
            ],
            "temperature": 0.25,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return _extract_response_text(data)


def _extract_response_text(data: dict[str, Any]) -> str:
    if data.get("output_text"):
        return str(data["output_text"]).strip()

    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip() or "No brief text returned."


def _generate_locally(
    event: dict[str, Any],
    lookup_context: dict[str, Any],
    error: str | None = None,
) -> str:
    title = event.get("title") or "Untitled meeting"
    start = event.get("start") or "Time not provided"
    description = _compact(sanitize_text(event.get("description") or "No description provided."), 240)
    attendees = event.get("attendees") or []
    prior_context = event.get("prior_context") or []
    domain_profiles = lookup_context.get("domain_profiles") or []

    context_lines = "\n".join(f"- {_compact(str(item), 180)}" for item in prior_context)
    context_lines = context_lines or "- No prior context provided."
    lookup_lines = "\n".join(_format_domain_profile(profile) for profile in domain_profiles)
    lookup_lines = lookup_lines or "- No external domain context."
    error_line = f"\nOpenAI note: {_compact(error, 180)}\n" if error else ""

    return f"""Meeting: {title}
Start: {start}

Who is joining:
{_format_attendees(attendees)}

Context:
- {description}
{context_lines}

Quick lookup:
{lookup_lines}

Remember:
- Confirm the other person's goal for the call early.
- Tie your answers to concrete shipped work, not abstract interest.
- Leave with a clear next step.

Questions to ask:
- What workflow is most painful or manual for the team right now?
- Where would automation save time without adding process overhead?
- What would make the next conversation useful for both sides?
{error_line}"""


def _format_attendees(attendees: list[Any]) -> str:
    lines = []
    for attendee in attendees:
        if isinstance(attendee, dict):
            email_domain = attendee_email_domain(attendee)
            name = attendee.get("name") or (f"person at {email_domain}" if email_domain else "") or "Unknown attendee"
            details = ", ".join(
                str(part)
                for part in [attendee.get("role"), attendee.get("company"), email_domain]
                if part
            )
            lines.append(f"- {name}" + (f" ({details})" if details else ""))
        else:
            lines.append(f"- {attendee}")
    return "\n".join(lines) or "- No attendees provided."


def _format_domain_profile(profile: dict[str, str]) -> str:
    pieces = [profile.get("domain", "unknown domain")]
    if profile.get("title"):
        pieces.append(profile["title"])
    if profile.get("description"):
        pieces.append(profile["description"])
    return "- " + " | ".join(pieces)


def _compact(value: Any, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
