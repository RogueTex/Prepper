from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import app


def main() -> None:
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ["NOTIFIER_PROVIDER"] = "console"
    client = app.app.test_client()

    with open("sample_event.json", encoding="utf-8") as file:
        payload = json.load(file)

    brief_response = client.post("/api/brief", json=payload)
    assert brief_response.status_code == 200, brief_response.get_data(as_text=True)
    brief_data = brief_response.get_json()
    assert brief_data["source"] == "local-fallback"
    assert "Product discovery call" in brief_data["brief"]

    sms_response = client.post("/api/sms", json={"body": "Synthetic test brief"})
    assert sms_response.status_code == 200
    assert sms_response.get_json()["status"] == "written"
    assert Path("outbox/latest_sms.txt").exists()

    events_response = client.get("/api/events?max_results=1")
    assert events_response.status_code == 500
    assert "Missing Google OAuth client file" in events_response.get_json()["error"]

    with patch("prep_brief.requests.post") as post:
        os.environ["OPENAI_API_KEY"] = "test-key"
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.return_value = {
            "output": [
                {
                    "content": [
                        {"text": "Context\n- Synthetic response\n\nRemember\n- Follow up\n\nQuestions\n- What matters most?"}
                    ]
                }
            ]
        }
        brief, source = app.generate_brief(payload)
        assert source == "openai"
        assert "Synthetic response" in brief
        request_json = post.call_args.kwargs["json"]
        assert request_json["model"]
        assert request_json["input"][0]["role"] == "system"

    print("smoke tests passed")


if __name__ == "__main__":
    main()
