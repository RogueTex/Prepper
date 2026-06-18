from __future__ import annotations

from flask import Flask, jsonify, render_template_string, request

from prep_brief import generate_brief


app = Flask(__name__)


INDEX_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Calendar Prep Flask</title>
    <style>
      body {
        max-width: 760px;
        margin: 40px auto;
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
        margin-top: 12px;
        padding: 10px 14px;
        border: 0;
        border-radius: 8px;
        background: #1f6feb;
        color: white;
        cursor: pointer;
        font-weight: 650;
      }
      pre {
        white-space: pre-wrap;
        background: #f6f8fa;
        border: 1px solid #d8dee4;
        border-radius: 8px;
        padding: 14px;
      }
    </style>
  </head>
  <body>
    <h1>Calendar Prep Flask</h1>
    <p>Paste meeting JSON and generate a quick prep brief.</p>
    <textarea id="payload">{
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
}</textarea>
    <br>
    <button onclick="generate()">Generate Brief</button>
    <h2>Brief</h2>
    <pre id="result">Waiting for input...</pre>
    <script>
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
          result.textContent = data.brief || JSON.stringify(data, null, 2);
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


@app.get("/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

