from flask import Flask, request, jsonify
import requests
from flask_cors import CORS 

app = Flask(__name__)
CORS(app)

API_KEY = "f94f7604c1a731a3ee54875f351bf026"

@app.route("/")
def get_aqi():
    lat = request.args.get("lat", "13.0827") 
    lon = request.args.get("lon", "80.2707")  

    url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
    
    response = requests.get(url)
    
    if response.status_code == 200:
        return jsonify(response.json())  
    else:
        return jsonify({"error": "Failed to fetch AQI data"}), response.status_code

if __name__ == "__main__":
    app.run(debug=True,port=5000)
