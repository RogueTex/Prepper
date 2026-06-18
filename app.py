from __future__ import annotations

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request

from calendar_client import list_upcoming_events
from notifier import send_sms
from prep_brief import generate_brief


load_dotenv()
app = Flask(__name__)


INDEX_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Calendar Prep</title>
    <style>
      body {
        max-width: 880px;
        margin: 36px auto;
        padding: 0 20px;
        font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: #1f2933;
        line-height: 1.55;
      }
      h1 { font-size: 28px; margin-bottom: 8px; }
      textarea {
        width: 100%;
        min-height: 260px;
        box-sizing: border-box;
        padding: 12px;
        border: 1px solid #cad3df;
        border-radius: 8px;
        font: 14px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      }
      button {
        margin: 8px 8px 8px 0;
        padding: 10px 14px;
        border: 0;
        border-radius: 8px;
        background: #1f6feb;
        color: white;
        cursor: pointer;
        font-weight: 650;
      }
      button.secondary { background: #516070; }
      pre {
        white-space: pre-wrap;
        background: #f6f8fa;
        border: 1px solid #d8dee4;
        border-radius: 8px;
        padding: 14px;
      }
      select, input {
        box-sizing: border-box;
        width: 100%;
        padding: 10px;
        border: 1px solid #cad3df;
        border-radius: 8px;
      }
      label { display: block; margin-top: 14px; font-weight: 650; }
    </style>
  </head>
  <body>
    <h1>Calendar Prep</h1>
    <p>Fetch upcoming Google Calendar events or paste meeting JSON, then generate prep notes locally.</p>

    <button onclick="loadEvents()">Fetch Calendar Events</button>
    <button class="secondary" onclick="generateUpcoming()">Brief Next 3 Events</button>

    <label for="events">Upcoming events</label>
    <select id="events" onchange="selectEvent()">
      <option value="">No calendar events loaded</option>
    </select>

    <label for="phone">SMS destination override</label>
    <input id="phone" placeholder="+15555555555 (optional; otherwise PREP_TO_NUMBER from .env)">

    <h2>Meeting JSON</h2>
    <textarea id="payload">{
  "title": "Product discovery call",
  "start": "2026-06-18T14:00:00-07:00",
  "end": "2026-06-18T14:30:00-07:00",
  "attendees": [
    {
      "name": "Alex Chen",
      "email": "alex@example.com",
      "company": "ExampleCo",
      "role": "Product Lead"
    }
  ],
  "description": "Introductory call about a workflow automation project.",
  "prior_context": [
    "Discussed reducing manual prep work before recurring customer calls.",
    "The team wants a lightweight tool that fits into existing calendar workflows."
  ]
}</textarea>
    <br>
    <button onclick="generate()">Generate Brief</button>
    <button class="secondary" onclick="sendCurrentSms()">Send Current Brief via SMS</button>
    <h2>Brief</h2>
    <pre id="result">Waiting for input...</pre>
    <script>
      let loadedEvents = [];
      let lastBrief = "";

      async function loadEvents() {
        const result = document.getElementById("result");
        const select = document.getElementById("events");
        result.textContent = "Fetching calendar events...";
        try {
          const response = await fetch("/api/events?max_results=8");
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || "Calendar fetch failed");
          loadedEvents = data.events || [];
          select.innerHTML = "";
          for (const [index, event] of loadedEvents.entries()) {
            const option = document.createElement("option");
            option.value = String(index);
            option.textContent = `${event.start || "No time"} - ${event.title}`;
            select.appendChild(option);
          }
          if (loadedEvents.length) {
            select.value = "0";
            selectEvent();
            result.textContent = `Loaded ${loadedEvents.length} events.`;
          } else {
            select.innerHTML = "<option>No upcoming events found</option>";
            result.textContent = "No upcoming events found.";
          }
        } catch (error) {
          result.textContent = String(error);
        }
      }

      function selectEvent() {
        const index = Number(document.getElementById("events").value);
        if (Number.isInteger(index) && loadedEvents[index]) {
          document.getElementById("payload").value = JSON.stringify(loadedEvents[index], null, 2);
        }
      }

      async function generate() {
        const result = document.getElementById("result");
        result.textContent = "Generating...";
        try {
          const payload = JSON.parse(document.getElementById("payload").value);
          const response = await fetch("/api/brief", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || "Brief generation failed");
          lastBrief = data.brief || "";
          result.textContent = lastBrief || JSON.stringify(data, null, 2);
        } catch (error) {
          result.textContent = String(error);
        }
      }

      async function generateUpcoming() {
        const result = document.getElementById("result");
        result.textContent = "Generating briefs for upcoming meetings...";
        try {
          const response = await fetch("/api/brief/upcoming?max_results=3", { method: "POST" });
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || "Brief generation failed");
          lastBrief = (data.briefs || [])
            .map((item, index) => `#${index + 1}: ${item.event.title}\nSource: ${item.source}\n\n${item.brief}`)
            .join("\n\n---\n\n");
          result.textContent = lastBrief;
        } catch (error) {
          result.textContent = String(error);
        }
      }

      async function sendCurrentSms() {
        const result = document.getElementById("result");
        try {
          if (!lastBrief) await generate();
          const response = await fetch("/api/sms", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              body: lastBrief || document.getElementById("result").textContent,
              to: document.getElementById("phone").value || undefined
            })
          });
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || "SMS failed");
          result.textContent = `${lastBrief}\n\nSMS queued: ${data.sid || "ok"}`;
        } catch (error) {
          result.textContent = String(error);
        }
      }
    </script>
  </body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(INDEX_HTML)


@app.post("/api/brief")
def brief():
    event = request.get_json(silent=True)
    if not isinstance(event, dict):
        return jsonify({"error": "Expected a JSON object."}), 400

    brief_text, source = generate_brief(event)
    return jsonify({"brief": brief_text, "source": source})


@app.get("/api/events")
def events():
    try:
        return jsonify({"events": list_upcoming_events(max_results=_max_results(default=5, cap=20))})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/brief/upcoming")
def brief_upcoming():
    try:
        events = list_upcoming_events(max_results=_max_results(default=3, cap=10))
        briefs = []
        for event in events:
            brief_text, source = generate_brief(event)
            briefs.append({"event": event, "brief": brief_text, "source": source})
        return jsonify({"briefs": briefs})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/sms")
def sms():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not payload.get("body"):
        return jsonify({"error": "Expected JSON with a non-empty body."}), 400

    try:
        result = send_sms(str(payload["body"]), to_number=payload.get("to"))
        return jsonify({"sid": result.get("sid"), "status": result.get("status"), "to": result.get("to")})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/health")
def health():
    return jsonify({"ok": True})


def _max_results(default: int, cap: int) -> int:
    raw = request.args.get("max_results", str(default))
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(1, min(value, cap))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
