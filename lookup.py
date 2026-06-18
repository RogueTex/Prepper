from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import requests


PERSONAL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "icloud.com",
    "me.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "proton.me",
    "protonmail.com",
}


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.description = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self.in_title = True
            return

        if tag.lower() != "meta":
            return

        attr_map = {key.lower(): value for key, value in attrs if value}
        name = (attr_map.get("name") or attr_map.get("property") or "").lower()
        if name in {"description", "og:description"} and attr_map.get("content"):
            self.description = attr_map["content"]

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join(part.strip() for part in self.title_parts if part.strip())


def enrich_event(event: dict[str, Any]) -> dict[str, Any]:
    domains = sorted(
        {
            domain
            for attendee in event.get("attendees", [])
            if (domain := _domain_from_attendee(attendee))
        }
    )
    return {
        "attendee_domains": domains,
        "domain_profiles": [_profile_domain(domain) for domain in domains],
    }


def _domain_from_attendee(attendee: Any) -> str:
    email = ""
    if isinstance(attendee, dict):
        email = attendee.get("email") or ""
    elif isinstance(attendee, str):
        email = attendee

    match = re.search(r"@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", email)
    if not match:
        return ""

    domain = match.group(1).lower().strip(".")
    if domain in PERSONAL_DOMAINS:
        return ""
    return domain


def _profile_domain(domain: str) -> dict[str, str]:
    profile = {"domain": domain}
    if os.getenv("ENABLE_DOMAIN_LOOKUP", "false").lower() not in {"1", "true", "yes"}:
        return profile

    metadata = _fetch_homepage_metadata(domain)
    if metadata:
        profile.update(metadata)
    return profile


def _fetch_homepage_metadata(domain: str) -> dict[str, str]:
    for url in (f"https://{domain}", f"https://www.{domain}"):
        try:
            response = requests.get(
                url,
                timeout=4,
                headers={"User-Agent": "calendar-prep-local/0.1"},
            )
            response.raise_for_status()
        except requests.RequestException:
            continue

        if "html" not in response.headers.get("content-type", ""):
            continue

        parser = MetadataParser()
        parser.feed(response.text[:100_000])
        return {
            "url": _origin(url),
            "title": parser.title[:180],
            "description": parser.description[:300],
        }
    return {}


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

