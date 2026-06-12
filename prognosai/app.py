"""
app.py
Flask application — PrognosAI web server.

Routes:
  GET  /           → renders the patient input form (index.html)
  GET  /results    → renders the results visualization page
  POST /analyze    → receives patient data, runs pipeline, returns JSON
  GET  /health     → simple health check
"""

from flask import Flask, render_template, request, jsonify
from engine.pipeline import run as pipeline_run

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/results")
def results():
    return render_template("results.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON body received"}), 400

        # Validate and parse habits (all 0.0 - 1.0)
        raw_habits = data.get("habits", {})
        habits = {}
        for key in ["smoking", "exercise", "diet", "alcohol", "bmi", "sleep"]:
            val = float(raw_habits.get(key, 0.0))
            habits[key] = max(0.0, min(1.0, val))

        budget = int(data.get("budget", 20))

        patient = {"habits": habits, "budget": budget}
        result = pipeline_run(patient)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
