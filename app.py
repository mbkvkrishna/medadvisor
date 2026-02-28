from flask import Flask, request, jsonify, render_template, session
from functools import wraps
from supabase_client import supabase
from rapidfuzz import process, fuzz
import os
import requests
import logging
import random
import string
import time
import hashlib
import secrets

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

for var in ["SUPABASE_URL", "SUPABASE_KEY", "MAILJET_API_KEY", "MAILJET_SECRET_KEY", "MAILJET_FROM_EMAIL", "SECRET_KEY"]:
    if not os.environ.get(var):
        logger.warning(f"Missing environment variable: {var}")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024

chat_sessions = {}
otp_store = {}
disease_cache = None
disease_cache_time = 0

OTP_EXPIRATION_TIME = 600
OTP_RATE_LIMIT_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
DISEASE_CACHE_TTL = 3600
SESSION_CLEANUP_INTERVAL = 3600
LAST_CLEANUP = time.time()


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()


def cleanup_expired_otps():
    current_time = time.time()
    expired = [e for e, d in otp_store.items() if current_time - d['timestamp'] > OTP_EXPIRATION_TIME]
    for email in expired:
        del otp_store[email]


def cleanup_sessions():
    global LAST_CLEANUP
    current_time = time.time()
    if current_time - LAST_CLEANUP > SESSION_CLEANUP_INTERVAL:
        chat_sessions.clear()
        LAST_CLEANUP = current_time
        logger.info("Sessions cleared")


def send_otp_email(email, otp):
    mj_api_key = os.environ.get("MAILJET_API_KEY")
    mj_secret_key = os.environ.get("MAILJET_SECRET_KEY")
    mj_from_email = os.environ.get("MAILJET_FROM_EMAIL")

    if not mj_api_key or not mj_secret_key or not mj_from_email:
        logger.warning(f"Mailjet not configured — OTP for {email} was generated but not sent")
        return False

    try:
        resp = requests.post(
            "https://api.mailjet.com/v3.1/send",
            auth=(mj_api_key, mj_secret_key),
            json={
                "Messages": [{
                    "From": {"Email": mj_from_email, "Name": "MedAdvisor"},
                    "To": [{"Email": email}],
                    "Subject": "MedAdvisor — Your One-Time Password",
                    "TextPart": (
                        f"Hello,\n\n"
                        f"Your MedAdvisor authentication code is:\n\n{otp}\n\n"
                        f"This code expires in 10 minutes.\n\n"
                        f"If you did not request this code, please ignore this email.\n\n"
                        f"Need help? Contact us at medadvisor.help@gmail.com\n\n"
                        f"Best regards,\nMedAdvisor Team"
                    ),
                    "HTMLPart": (
                        f"<div style='font-family:system-ui,Arial,sans-serif;max-width:480px;margin:auto;padding:32px;background:#0a0a0a;color:#fff;border-radius:10px;'>"
                        f"<h2 style='margin:0 0 8px 0;font-size:20px;'>MedAdvisor</h2>"
                        f"<p style='color:#888;margin:0 0 28px 0;font-size:13px;'>Smart HealthCare</p>"
                        f"<p style='margin:0 0 12px 0;'>Hello,</p>"
                        f"<p style='margin:0 0 20px 0;'>Your MedAdvisor authentication code is:</p>"
                        f"<div style='background:#111;border:1px solid #333;border-radius:8px;padding:20px;text-align:center;margin:0 0 24px 0;'>"
                        f"<span style='font-size:36px;font-weight:700;letter-spacing:10px;color:#8fccaa;'>{otp}</span>"
                        f"</div>"
                        f"<p style='color:#aaa;font-size:14px;margin:0 0 8px 0;'>This code expires in <strong>10 minutes</strong>.</p>"
                        f"<p style='color:#aaa;font-size:14px;margin:0 0 24px 0;'>If you did not request this code, please ignore this email.</p>"
                        f"<hr style='border:none;border-top:1px solid #222;margin:0 0 20px 0;'>"
                        f"<p style='color:#666;font-size:12px;margin:0;'>Need help? Contact us at "
                        f"<a href='mailto:medadvisor.help@gmail.com' style='color:#8fccaa;'>medadvisor.help@gmail.com</a></p>"
                        f"</div>"
                    )
                }]
            },
            timeout=10
        )
        if resp.status_code == 200:
            logger.info(f"OTP sent to {email}")
            return True
        logger.error(f"Mailjet error {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Email send error: {e}")
        return False


def load_diseases():
    global disease_cache, disease_cache_time
    now = time.time()
    if disease_cache is None or (now - disease_cache_time) > DISEASE_CACHE_TTL:
        try:
            resp = supabase.table("diseases").select("*").execute()
            disease_cache = resp.data or []
            disease_cache_time = now
            logger.info(f"Loaded {len(disease_cache)} diseases from Supabase")
        except Exception as e:
            logger.error(f"Failed to load diseases: {e}")
            return disease_cache or []
    return disease_cache


def find_disease(user_input):
    diseases = load_diseases()
    if not diseases:
        logger.warning("Disease cache is empty — check Supabase connection")
        return None

    query = user_input.lower().strip()
    names = [d["name"].lower() for d in diseases]

    for d in diseases:
        if d["name"].lower() == query:
            return d

    for d in diseases:
        if query in d["name"].lower() or d["name"].lower().startswith(query):
            return d

    best_score = 0
    best_match = None

    for scorer in [fuzz.token_set_ratio, fuzz.partial_ratio, fuzz.ratio]:
        match = process.extractOne(query, names, scorer=scorer)
        if match and match[1] > best_score:
            best_score = match[1]
            best_match = match

    threshold = 60 if len(query) <= 5 else 65

    if best_match and best_score >= threshold:
        for d in diseases:
            if d["name"].lower() == best_match[0]:
                return d

    return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('email'):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@app.route("/auth/send-authentication-link", methods=["POST"])
def send_authentication_link():
    try:
        cleanup_expired_otps()
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        email = data.get("email", "").strip().lower()
        if not email or "@" not in email:
            return jsonify({"error": "Valid email is required"}), 400

        if email in otp_store:
            elapsed = time.time() - otp_store[email]['timestamp']
            if elapsed < OTP_RATE_LIMIT_SECONDS:
                wait = int(OTP_RATE_LIMIT_SECONDS - elapsed)
                return jsonify({"error": f"Please wait {wait}s before requesting another OTP"}), 429

        otp = generate_otp()
        otp_store[email] = {
            "otp_hash": hash_otp(otp),
            "timestamp": time.time(),
            "attempts": 0
        }

        if not send_otp_email(email, otp):
            del otp_store[email]
            return jsonify({"error": "Failed to send OTP. Please try again later"}), 500

        return jsonify({"success": True, "message": "OTP sent to your email"}), 200

    except Exception as e:
        logger.error(f"send_authentication_link: {e}")
        return jsonify({"error": "An error occurred. Please try again"}), 500


@app.route("/auth/verify-otp", methods=["POST"])
def verify_otp():
    try:
        cleanup_expired_otps()
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        email = data.get("email", "").strip().lower()
        otp = data.get("otp", "").strip()
        name = data.get("name", "").strip()

        if not email or not otp:
            return jsonify({"error": "Email and OTP are required"}), 400

        if email not in otp_store:
            return jsonify({"error": "OTP not found or expired. Please request a new one."}), 401

        stored = otp_store[email]

        if time.time() - stored['timestamp'] > OTP_EXPIRATION_TIME:
            del otp_store[email]
            return jsonify({"error": "OTP expired. Please request a new one."}), 401

        if stored['attempts'] >= OTP_MAX_ATTEMPTS:
            del otp_store[email]
            return jsonify({"error": "Too many incorrect attempts. Please request a new OTP."}), 429

        stored['attempts'] += 1

        if stored['otp_hash'] != hash_otp(otp):
            remaining = OTP_MAX_ATTEMPTS - stored['attempts']
            return jsonify({"error": f"Invalid OTP. {remaining} attempt(s) remaining."}), 401

        del otp_store[email]

        try:
            supabase.table("users").upsert({"email": email, "name": name or ""}).execute()
            logger.info(f"User upserted: {email}")
        except Exception as db_err:
            logger.error(f"DB error upserting user: {db_err}")

        session['email'] = email
        session['name'] = name or ""

        return jsonify({"success": True, "email": email, "name": name}), 200

    except Exception as e:
        logger.error(f"verify_otp: {e}")
        return jsonify({"error": "An error occurred. Please try again"}), 500


@app.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True}), 200


@app.route("/auth/delete-account", methods=["POST"])
@require_auth
def delete_account():
    try:
        email = session['email']
        try:
            supabase.table("saved_results").delete().eq("user_id", email).execute()
            supabase.table("users").delete().eq("email", email).execute()
            logger.info(f"Account deleted: {email}")
        except Exception as db_err:
            logger.error(f"DB error deleting account: {db_err}")
            return jsonify({"error": "Failed to delete account"}), 500

        session.clear()
        return jsonify({"success": True}), 200

    except Exception as e:
        logger.error(f"delete_account: {e}")
        return jsonify({"error": "An error occurred"}), 500


@app.route("/chat", methods=["POST"])
def chat():
    try:
        cleanup_sessions()
        data = request.get_json()
        if not data:
            return jsonify({"reply": "Invalid request.", "input": "disease"}), 400

        user_id = data.get("user_id", "").strip()
        message = data.get("message", "").strip()

        if not user_id:
            return jsonify({"reply": "Session error. Please refresh.", "input": "disease"}), 400
        if not message:
            return jsonify({"reply": "Please enter a message.", "input": "disease"}), 400
        if len(message) > 500:
            return jsonify({"reply": "Input too long. Please try again.", "input": "disease"}), 400

        if user_id not in chat_sessions:
            chat_sessions[user_id] = {"step": "disease", "created": time.time()}

        state = chat_sessions[user_id]

        if state["step"] == "disease":
            disease = find_disease(message)
            if not disease:
                return jsonify({
                    "reply": "Disease not found. Please try a different name.",
                    "input": "disease"
                }), 200
            state["disease"] = disease
            state["step"] = "age"
            return jsonify({
                "reply": f"Found: {disease['name']}\n\nEnter patient age:",
                "input": "age"
            }), 200

        elif state["step"] == "age":
            if not message.isdigit():
                return jsonify({"reply": "Please enter a valid age (numbers only).", "input": "age"}), 200
            age = int(message)
            if age < 0 or age > 120:
                return jsonify({"reply": "Please enter a realistic age (0–120).", "input": "age"}), 200
            state["age"] = age
            state["step"] = "gender"
            return jsonify({
                "reply": "Select gender:",
                "input": "gender",
                "options": ["Male", "Female"]
            }), 200

        elif state["step"] == "gender":
            gender = message.lower()
            if gender not in ["male", "female"]:
                return jsonify({
                    "reply": "Please select gender using the buttons.",
                    "input": "gender",
                    "options": ["Male", "Female"]
                }), 200

            disease = state.get("disease")
            age = state.get("age")

            if not disease or age is None:
                chat_sessions[user_id] = {"step": "disease", "created": time.time()}
                return jsonify({"reply": "Session error. Please start over.", "input": "disease"}), 400

            medicines = disease.get("medicines", [])
            results = []
            for m in medicines:
                if m.get("min_age", 0) <= age <= m.get("max_age", 120):
                    text = (
                        f"{m.get('name', 'Unknown')}\n"
                        f"Dosage: {m.get('dosage', 'N/A')}\n"
                        f"{m.get('description', '')}\n"
                        f"Cost: {m.get('cost', 'N/A')}"
                    )
                    if gender == "female" and m.get("female_precautions"):
                        text += f"\nPrecautions: {m['female_precautions']}"
                    results.append(text)

            chat_sessions[user_id] = {"step": "disease", "created": time.time()}

            if not results:
                return jsonify({
                    "reply": "No medicines found for this age group. Please consult a doctor.",
                    "input": "disease"
                }), 200

            return jsonify({
                "reply": "\n\n".join(results),
                "input": "disease",
                "disease_name": disease.get("name", "Unknown"),
                "can_save": True
            }), 200

        else:
            chat_sessions[user_id] = {"step": "disease", "created": time.time()}
            return jsonify({"reply": "Something went wrong. Please start over.", "input": "disease"}), 400

    except Exception as e:
        logger.error(f"chat: {e}")
        return jsonify({"reply": "An error occurred. Please try again.", "input": "disease"}), 500


@app.route("/results/save", methods=["POST"])
@require_auth
def save_result():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400

        email = session['email']
        disease_name = data.get("disease_name", "").strip()
        medicine_output = data.get("medicine_output", "").strip()

        if not all([disease_name, medicine_output]):
            return jsonify({"error": "Missing required fields"}), 400

        if len(medicine_output) > 10000:
            return jsonify({"error": "Output too large to save"}), 400

        try:
            resp = supabase.table("saved_results").insert({
                "user_id": email,
                "disease_name": disease_name,
                "medicine_output": medicine_output
            }).execute()
            logger.info(f"Result saved for: {email}")
        except Exception as db_err:
            logger.error(f"DB error saving result: {db_err}")
            return jsonify({"error": "Failed to save result"}), 500

        return jsonify({
            "success": True,
            "saved_result": resp.data[0] if resp.data else None
        }), 200

    except Exception as e:
        logger.error(f"save_result: {e}")
        return jsonify({"error": "An error occurred"}), 500


@app.route("/results/get", methods=["GET"])
@require_auth
def get_results():
    try:
        email = session['email']
        try:
            resp = supabase.table("saved_results").select("*").eq("user_id", email).order("created_at", desc=True).execute()
            logger.info(f"Results fetched for: {email}")
        except Exception as db_err:
            logger.error(f"DB error fetching results: {db_err}")
            return jsonify({"error": "Failed to retrieve results"}), 500

        return jsonify({"results": resp.data or []}), 200

    except Exception as e:
        logger.error(f"get_results: {e}")
        return jsonify({"error": "An error occurred"}), 500


@app.route("/results/delete/<int:result_id>", methods=["DELETE"])
@require_auth
def delete_result(result_id):
    try:
        email = session['email']
        try:
            supabase.table("saved_results").delete().eq("id", result_id).eq("user_id", email).execute()
            logger.info(f"Result {result_id} deleted for: {email}")
        except Exception as db_err:
            logger.error(f"DB error deleting result: {db_err}")
            return jsonify({"error": "Failed to delete result"}), 500

        return jsonify({"success": True}), 200

    except Exception as e:
        logger.error(f"delete_result: {e}")
        return jsonify({"error": "An error occurred"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_ENV") == "development"
    logger.info(f"Starting MedAdvisor on 0.0.0.0:{port} (debug={debug_mode})")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
