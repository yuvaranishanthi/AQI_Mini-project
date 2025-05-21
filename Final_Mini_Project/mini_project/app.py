from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
import requests
import os
import fitz  
import joblib
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_super_secret_key_here'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# MongoDB setup
client = MongoClient("mongodb://localhost:27017/")
db = client["AQI"]
users_collection = db["users"]

API_KEY = "f94f7604c1a731a3ee54875f351bf026"

AQI_CATEGORIES = {
    1: ("Good", "#00E400", "Low Risk"),
    2: ("Fair", "#9CFF9C", "Slight Risk"),
    3: ("Moderate", "#FFFF00", "Moderate Risk"),
    4: ("Poor", "#FF7E00", "High Risk"),
    5: ("Very Poor", "#FF0000", "Very High Risk")
}

model = joblib.load("condition_classifier.pkl")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(filepath):
    text = ""
    try:
        doc = fitz.open(filepath)
        for page in doc:
            text += page.get_text()
        return text
    except Exception:
        return ""

def predict_condition(text):
    return model.predict([text])[0]

def generate_advice(condition, aqi_value):
    if condition == "asthma" and aqi_value >= 100:
        return "⚠️ Not safe to go out due to asthma and high AQI."
    elif condition == "heart_disease" and aqi_value >= 100:
        return "⚠️ Not safe to go out due to heart condition and high AQI."
    elif aqi_value >= 150:
        return "⚠️ AQI is very poor. Avoid going out."
    else:
        return "✅ Safe to go out."

@app.route('/')
def serve_home():
    return render_template('home.html')

@app.route('/register_page')
def serve_register():
    return render_template('register.html')

@app.route('/login_page')
def serve_login():
    return render_template('login.html')  
@app.route('/aqi_page')
def serve_aqi():
    if not session.get('email'):
        return redirect(url_for('serve_login'))
    return render_template('index.html')

@app.route('/upload_page')
def serve_upload():
    if not session.get('email'):
        return redirect(url_for('serve_login'))
    return render_template('upload.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password required"}), 400

    existing_user = users_collection.find_one({"email": email})
    if existing_user:
        return jsonify({"message": "User already exists"}), 400

    hashed_password = generate_password_hash(password)
    users_collection.insert_one({"email": email, "password": hashed_password})
    return jsonify({"message": "Registration successful"}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password required"}), 400

    user = users_collection.find_one({"email": email})
    if not user or not check_password_hash(user['password'], password):
        return jsonify({"message": "Invalid credentials"}), 401

    session['email'] = email
    return jsonify({"message": "Login successful"}), 200

@app.route('/logout')
def logout():
    session.pop('email', None)
    session.pop('condition', None)
    return redirect(url_for('serve_home'))

@app.route('/upload_report', methods=['POST'])
def upload_report():
    if 'report' not in request.files:
        return jsonify({"message": "File missing"}), 400
    if 'email' not in session:
        return jsonify({"message": "User not logged in"}), 401

    file = request.files['report']
    email = session['email']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], email + "_" + filename)
        file.save(file_path)

        extracted_text = extract_text_from_pdf(file_path)
        condition = predict_condition(extracted_text)
        session['condition'] = condition  # Save condition for later AQI advice

        return jsonify({
            "condition": condition,
            "message": "Report uploaded and condition predicted successfully. Now fetch AQI."
        }), 200
    else:
        return jsonify({"message": "Invalid file type"}), 400

@app.route('/get_aqi', methods=['GET'])
def get_aqi():
    if 'email' not in session:
        return jsonify({"message": "User not logged in"}), 401
    if 'condition' not in session:
        return jsonify({"message": "Please upload medical report first."}), 400

    destination = request.args.get("destination")
    if not destination:
        return jsonify({"message": "Destination required"}), 400

    geocode_url = f"http://api.openweathermap.org/geo/1.0/direct?q={destination}&limit=1&appid={API_KEY}"
    geocode_response = requests.get(geocode_url)
    if geocode_response.status_code != 200 or not geocode_response.json():
        return jsonify({"message": "Failed to get location coordinates"}), 500

    location_data = geocode_response.json()[0]
    lat = location_data["lat"]
    lon = location_data["lon"]

    aqi_url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    aqi_response = requests.get(aqi_url)

    if aqi_response.status_code == 200:
        aqi_data = aqi_response.json()
        aqi_index = aqi_data["list"][0]["main"]["aqi"]
        category, color, asthma_risk = AQI_CATEGORIES.get(aqi_index, ("Unknown", "#999", "Unknown Risk"))

        aqi_value_mapping = {
            1: 50,
            2: 75,
            3: 100,
            4: 150,
            5: 200
        }
        aqi_value = aqi_value_mapping.get(aqi_index, 100)

        condition = session.get('condition')
        advice = generate_advice(condition, aqi_value)

        return jsonify({
            "aqi_index": aqi_index,
            "aqi_value_estimated": aqi_value,
            "aqi_category": category,
            "color": color,
            "risk_level": asthma_risk,
            "condition": condition,
            "advice": advice,
            "location": {
                "destination": destination,
                "latitude": lat,
                "longitude": lon
            }
        })
    else:
        return jsonify({"message": "Failed to get AQI data"}), 500

if __name__ == '__main__':
    app.run(debug=True)



# from flask import Flask, request, jsonify, render_template, session, redirect, url_for
# from flask_cors import CORS
# import requests
# import os
# import fitz  # PyMuPDF
# import joblib
# from werkzeug.utils import secure_filename
# from werkzeug.security import generate_password_hash, check_password_hash

# app = Flask(__name__)
# CORS(app)
# app.secret_key = 'your_super_secret_key_here'
# UPLOAD_FOLDER = 'uploads'
# ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# users = {}
# API_KEY = "f94f7604c1a731a3ee54875f351bf026"

# AQI_CATEGORIES = {
#     1: ("Good", "#00E400", "Low Risk"),
#     2: ("Fair", "#9CFF9C", "Slight Risk"),
#     3: ("Moderate", "#FFFF00", "Moderate Risk"),
#     4: ("Poor", "#FF7E00", "High Risk"),
#     5: ("Very Poor", "#FF0000", "Very High Risk")
# }

# # Load ML model
# model = joblib.load("condition_classifier.pkl")

# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# def extract_text_from_pdf(filepath):
#     text = ""
#     try:
#         doc = fitz.open(filepath)
#         for page in doc:
#             text += page.get_text()
#         return text
#     except Exception:
#         return ""

# def predict_condition(text):
#     return model.predict([text])[0]

# def generate_advice(condition, aqi_value):
#     if condition == "asthma" and aqi_value >= 100:
#         return "⚠️ Not safe to go out due to asthma and high AQI."
#     elif condition == "heart_disease" and aqi_value >= 100:
#         return "⚠️ Not safe to go out due to heart condition and high AQI."
#     elif aqi_value >= 150:
#         return "⚠️ AQI is very poor. Avoid going out."
#     else:
#         return "✅ Safe to go out."

# @app.route('/')
# def serve_home():
#     return render_template('home.html')

# @app.route('/register_page')
# def serve_register():
#     if session.get('email'):
#         return redirect(url_for('serve_aqi'))
#     return render_template('register.html')

# @app.route('/login_page')
# def serve_login():
#     if session.get('email'):
#         return redirect(url_for('serve_aqi'))
#     return render_template('login.html')

# @app.route('/aqi_page')
# def serve_aqi():
#     if not session.get('email'):
#         return redirect(url_for('serve_login'))
#     return render_template('index.html')

# @app.route('/upload_page')
# def serve_upload():
#     if not session.get('email'):
#         return redirect(url_for('serve_login'))
#     return render_template('upload.html')

# @app.route('/register', methods=['POST'])
# def register():
#     data = request.get_json()
#     email = data.get("email")
#     password = data.get("password")
#     if not email or not password:
#         return jsonify({"message": "Email and password required"}), 400
#     if email in users:
#         return jsonify({"message": "User already exists"}), 400
#     hashed_password = generate_password_hash(password)
#     users[email] = hashed_password
#     return jsonify({"message": "Registration successful"}), 200

# @app.route('/login', methods=['POST'])
# def login():
#     data = request.get_json()
#     email = data.get("email")
#     password = data.get("password")
#     if not email or not password:
#         return jsonify({"message": "Email and password required"}), 400
#     stored_hash = users.get(email)
#     if not stored_hash or not check_password_hash(stored_hash, password):
#         return jsonify({"message": "Invalid credentials"}), 401
#     session['email'] = email
#     return jsonify({"message": "Login successful"}), 200

# @app.route('/logout')
# def logout():
#     session.pop('email', None)
#     session.pop('condition', None)
#     return redirect(url_for('serve_home'))

# @app.route('/upload_report', methods=['POST'])
# def upload_report():
#     if 'report' not in request.files:
#         return jsonify({"message": "File missing"}), 400
#     if 'email' not in session:
#         return jsonify({"message": "User not logged in"}), 401

#     file = request.files['report']
#     email = session['email']
#     if file and allowed_file(file.filename):
#         filename = secure_filename(file.filename)
#         file_path = os.path.join(app.config['UPLOAD_FOLDER'], email + "_" + filename)
#         file.save(file_path)

#         extracted_text = extract_text_from_pdf(file_path)
#         condition = predict_condition(extracted_text)
#         session['condition'] = condition  # Save condition for later AQI advice

#         return jsonify({
#             "condition": condition,
#             "message": "Report uploaded and condition predicted successfully. Now fetch AQI."
#         }), 200
#     else:
#         return jsonify({"message": "Invalid file type"}), 400

# @app.route('/get_aqi', methods=['GET'])
# def get_aqi():
#     if 'email' not in session:
#         return jsonify({"message": "User not logged in"}), 401
#     if 'condition' not in session:
#         return jsonify({"message": "Please upload medical report first."}), 400

#     destination = request.args.get("destination")
#     if not destination:
#         return jsonify({"message": "Destination required"}), 400

#     geocode_url = f"http://api.openweathermap.org/geo/1.0/direct?q={destination}&limit=1&appid={API_KEY}"
#     geocode_response = requests.get(geocode_url)
#     if geocode_response.status_code != 200 or not geocode_response.json():
#         return jsonify({"message": "Failed to get location coordinates"}), 500

#     location_data = geocode_response.json()[0]
#     lat = location_data["lat"]
#     lon = location_data["lon"]

#     aqi_url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
#     aqi_response = requests.get(aqi_url)

#     if aqi_response.status_code == 200:
#         aqi_data = aqi_response.json()
#         aqi_index = aqi_data["list"][0]["main"]["aqi"]
#         category, color, asthma_risk = AQI_CATEGORIES.get(aqi_index, ("Unknown", "#999", "Unknown Risk"))

#         # AQI value mapping to estimated index
#         aqi_value_mapping = {
#             1: 50,
#             2: 75,
#             3: 100,
#             4: 150,
#             5: 200
#         }
#         aqi_value = aqi_value_mapping.get(aqi_index, 100)

#         condition = session.get('condition')
#         advice = generate_advice(condition, aqi_value)

#         return jsonify({
#             "aqi_index": aqi_index,
#             "aqi_value_estimated": aqi_value,
#             "aqi_category": category,
#             "color": color,
#             "risk_level": asthma_risk,
#             "condition": condition,
#             "advice": advice,
#             "location": {
#                 "destination": destination,
#                 "latitude": lat,
#                 "longitude": lon
#             }
#         })
#     else:
#         return jsonify({"message": "Failed to get AQI data"}), 500

# if __name__ == '__main__':
#     app.run(debug=True)
