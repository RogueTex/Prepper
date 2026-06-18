from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import app
import doctor
import reminder_worker


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

    os.environ["CALENDAR_SOURCE"] = "google_api"
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
        assert "alex@example.com" not in json.dumps(request_json)
        assert "email_domain" in json.dumps(request_json)

    with patch("doctor.list_upcoming_events") as events, patch("doctor.generate_brief") as brief_fn, patch(
        "doctor.send_sms"
    ) as send:
        events.return_value = [{"id": "synthetic", "title": "Synthetic", "start": "2099-01-01T12:00:00"}]
        brief_fn.return_value = ("Synthetic brief", "local-fallback")
        send.return_value = {"status": "written", "to": "console"}
        doctor.run_probe()
        send.assert_called_once()
        assert "Synthetic brief" in send.call_args.args[0]

    with patch("reminder_worker.list_upcoming_events") as events, patch("reminder_worker.generate_brief") as brief_fn, patch(
        "reminder_worker.send_sms"
    ) as send:
        with tempfile.TemporaryDirectory() as temp_dir:
            reminder_worker.STATE_FILE = Path(temp_dir) / "sent_reminders.json"
            events.return_value = [{"id": "synthetic-once", "title": "Synthetic", "start": "2099-01-01T12:00:00"}]
            brief_fn.return_value = ("Synthetic brief", "local-fallback")
            send.return_value = {"status": "written", "to": "console"}
            count = reminder_worker.run_once(max_results=1)
            assert count == 1
            send.assert_called_once()

    print("smoke tests passed")


if __name__ == "__main__":
    main()
