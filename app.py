from flask import Flask, render_template, request, jsonify, session, redirect
from supabase import create_client
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

@app.route("/")
def index():
    return render_template("index.html", user=session.get("user"))

@app.route("/login")
def login_page():
    return render_template("login.html", user=session.get("user"))

@app.route("/signup")
def signup_page():
    return render_template("signup.html", user=session.get("user"))

@app.route("/results")
def results():
    return render_template("results.html", user=session.get("user"))

@app.route("/bookmarks")
def bookmarks_page():
    if "user" not in session:
        return redirect("/login")
    return render_template("bookmarks.html", user=session.get("user"))

@app.route("/signup_user", methods=["POST"])
def signup_user():
    data = request.json
    username = data["username"]
    password = data["password"]
    existing = supabase.table("users").select("*").eq("username", username).execute()
    if existing.data:
        return jsonify({"success": False})
    response = supabase.table("users").insert({
        "username": username,
        "password": password,
        "display_name": username,
        "theme": "light"
    }).execute()
    session["user"] = response.data[0]
    return jsonify({"success": True})

@app.route("/login_user", methods=["POST"])
def login_user():
    data = request.json
    username = data["username"]
    password = data["password"]
    response = supabase.table("users").select("*").eq("username", username).eq("password", password).execute()
    if not response.data:
        return jsonify({"success": False})
    session["user"] = response.data[0]
    return jsonify({"success": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

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
    return jsonify({"medicines": medicines, "description": description, "disease": disease_input})

@app.route("/save_search", methods=["POST"])
def save_search():
    if "user" not in session:
        return jsonify({"success": False})
    data = request.json
    supabase.table("searches").insert({
        "user_id": session["user"]["id"],
        "disease": data["disease"],
        "age": data["age"],
        "gender": data["gender"]
    }).execute()
    return jsonify({"success": True})

@app.route("/get_recent")
def get_recent():
    if "user" not in session:
        return jsonify({"searches": []})
    response = supabase.table("searches").select("*").eq("user_id", session["user"]["id"]).order("created_at", desc=True).limit(5).execute()
    return jsonify({"searches": response.data})

@app.route("/bookmark", methods=["POST"])
def bookmark():
    if "user" not in session:
        return jsonify({"success": False})
    data = request.json
    supabase.table("bookmarks").insert({
        "user_id": session["user"]["id"],
        "disease": data["disease"],
        "result": data["result"]
    }).execute()
    return jsonify({"success": True})

@app.route("/get_bookmarks")
def get_bookmarks():
    if "user" not in session:
        return jsonify({"bookmarks": []})
    response = supabase.table("bookmarks").select("*").eq("user_id", session["user"]["id"]).order("created_at", desc=True).execute()
    return jsonify({"bookmarks": response.data})

@app.route("/delete_account", methods=["POST"])
def delete_account():
    if "user" not in session:
        return jsonify({"success": False})
    user_id = session["user"]["id"]
    supabase.table("bookmarks").delete().eq("user_id", user_id).execute()
    supabase.table("searches").delete().eq("user_id", user_id).execute()
    supabase.table("users").delete().eq("id", user_id).execute()
    session.clear()
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)
