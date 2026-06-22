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

        raw_habits = data.get("habits", {})
        habits = {}
        for key in ["smoking", "exercise", "diet", "alcohol", "bmi", "sleep"]:
            val = float(raw_habits.get(key, 0.0))
            habits[key] = max(0.0, min(1.0, val))

        budget = int(data.get("budget", 15))
        budget = max(3, min(50, budget))

        patient = {
            "firstName":          data.get("firstName", ""),
            "lastName":           data.get("lastName", ""),
            "age":                data.get("age"),
            "gender":             data.get("gender", ""),
            "weight":             data.get("weight"),
            "height":             data.get("height"),
            "bmi":                data.get("bmi"),
            "smokingStatus":      data.get("smokingStatus", "never"),
            "familyHistory":      data.get("familyHistory", "none"),
            "existingConditions": data.get("existingConditions", "none"),
            "weeklyHours":        data.get("weeklyHours", 5),
            "habits":             habits,
            "budget":             budget,
        }

        result = pipeline_run(patient)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)