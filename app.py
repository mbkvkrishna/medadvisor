from flask import Flask, render_template, request, jsonify
from supabase import create_client
import os

app = Flask(__name__)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_diseases", methods=["POST"])
def get_diseases():
    query = request.json.get("disease", "").strip()
    if not query:
        return jsonify({"diseases": []})
    response = supabase.table("medicines").select("disease").ilike("disease", f"%{query}%").execute()
    diseases = list({row["disease"] for row in response.data})
    return jsonify({"diseases": diseases})

@app.route("/get_medicines", methods=["POST"])
def get_medicines():
    data = request.json
    disease_input = data.get("disease", "").strip()
    age = int(data.get("age", 0))
    gender = data.get("gender", "")

    response = supabase.table("medicines").select("*").eq("disease", disease_input).execute()
    if not response.data:
        return jsonify({"medicines": [], "description": ""})

    medicines = []
    description = response.data[0]["description"]

    for med in response.data:
        dosage = med["dosage_child"] if age < 12 else med["dosage_adult"]
        precautions = med["precautions"]
        if gender == "female":
            precautions = precautions + ". " + med["female_precautions"]
        medicines.append({
            "name": med["medicine_name"],
            "cost": med["cost_inr"],
            "dosage": dosage,
            "precautions": precautions
        })

    return jsonify({"medicines": medicines, "description": description})
