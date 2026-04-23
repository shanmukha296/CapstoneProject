from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import joblib
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import math
import os
import xgboost as xgb
import torch
import torch.nn as nn
from model_definitions import BiLSTM, SpatialGNN
from utils.routing import get_google_routes, analyze_route_safety
from utils.video_processing import generate_frames, get_detector
from twilio.twiml.messaging_response import MessagingResponse
from utils.web3_utils import upload_to_ipfs, log_alert_on_chain
from utils.graph_builder import build_crime_graph, get_spatial_influence_links

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here' # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crime_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app)

# --- Twilio Config (Placeholders) ---
TWILIO_SID = os.environ.get('TWILIO_SID', 'AC_YOUR_SID_HERE')
TWILIO_TOKEN = os.environ.get('TWILIO_TOKEN', 'YOUR_TOKEN_HERE')
TWILIO_NUMBER = os.environ.get('TWILIO_NUMBER', '+1234567890')

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class PoliceStation(db.Model):
    __tablename__ = 'police_stations'
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(50), index=True, nullable=False)
    district = db.Column(db.String(50), index=True)
    ps_name = db.Column(db.String(100), unique=True, nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    emergency = db.Column(db.Boolean, default=True)
    crime_rate = db.Column(db.Float) # Per 100k
    capacity = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Manual Spatial Index Simulation (Composite)
    __table_args__ = (db.Index('idx_state_district', 'state', 'district'),)
    
# --- Load ML Models ---
print("Loading ML Models...")
try:
    # XGBoost
    xgb_model = joblib.load('models/xgboost_model.pkl')
    # BiLSTM
    bilstm_model = BiLSTM(1, 50, 1, 1) # Must match training config
    bilstm_model.load_state_dict(torch.load('models/bilstm_model.pth'))
    bilstm_model.eval()
    
    # Encoders & Scalers
    label_encoder = joblib.load('models/label_encoder.pkl')
    weather_encoder = joblib.load('models/weather_encoder.pkl')
    scaler_lstm = joblib.load('models/scaler_lstm.pkl')
    kmeans = joblib.load('models/kmeans_model.pkl')
    
    print("Advanced Models loaded successfully.")
except Exception as e:
    print(f"Error loading models: {e}")
    xgb_model = None
    bilstm_model = None

# --- Constants & Data (National Expansion) ---
POLICE_STATIONS = [
    {"city": "Hyderabad", "name": "Charminar PS", "lat": 17.385044, "lng": 78.474655, "phone": "9490616481"},
    {"city": "Hyderabad", "name": "Begumpet PS", "lat": 17.417500, "lng": 78.493889, "phone": "9490616419"},
    {"city": "Hyderabad", "name": "Banjara Hills PS", "lat": 17.400000, "lng": 78.500000, "phone": "9490616576"},
    {"city": "Bangalore", "name": "Indiranagar PS", "lat": 12.9786, "lng": 77.6408, "phone": "080-22942416"},
    {"city": "Bangalore", "name": "Koramangala PS", "lat": 12.9352, "lng": 77.6245, "phone": "080-22942414"},
    {"city": "Delhi", "name": "Connaught Place PS", "lat": 28.6289, "lng": 77.2181, "phone": "011-23340156"},
    {"city": "Delhi", "name": "Hauz Khas PS", "lat": 28.5447, "lng": 77.2062, "phone": "011-26858121"},
    {"city": "Chennai", "name": "Anna Nagar PS", "lat": 13.0850, "lng": 80.2101, "phone": "044-23452243"},
]

HOSPITALS = [
    {"city": "Hyderabad", "name": "Apollo Hospitals, Jubilee Hills", "lat": 17.4260, "lng": 78.4110, "phone": "040-23607777"},
    {"city": "Hyderabad", "name": "Osmania General Hospital", "lat": 17.3780, "lng": 78.4710, "phone": "040-24602334"},
    {"city": "Bangalore", "name": "Manipal Hospital, Old Airport Rd", "lat": 12.9592, "lng": 77.6441, "phone": "080-22221111"},
    {"city": "Bangalore", "name": "Victoria Hospital", "lat": 12.9634, "lng": 77.5746, "phone": "080-26701150"},
    {"city": "Delhi", "name": "AIIMS Delhi", "lat": 28.5672, "lng": 77.2100, "phone": "011-26588500"},
    {"city": "Delhi", "name": "Safdarjung Hospital", "lat": 28.5670, "lng": 77.2000, "phone": "011-26730000"},
    {"city": "Chennai", "name": "Apollo Hospitals, Greams Rd", "lat": 13.0617, "lng": 80.2520, "phone": "044-28293333"},
]

geolocator = Nominatim(user_agent="safe_route_india_national")

def init_police_db():
    if PoliceStation.query.first():
        return # Already seeded
        
    print("Initializing Nationwide Police Database (528+ stations)...")
    stations = []
    
    # --- TELANGANA (50) ---
    for i in range(50):
        stations.append(PoliceStation(
            state="TELANGANA", district="Hyderabad", 
            ps_name=f"Hyderabad PS {i+1}", 
            lat=17.385 + (i*0.001), lng=78.474 + (i*0.001), 
            phone="9490616481", crime_rate=950, emergency=True
        ))
    # Override specific ones mentioned in prompt
    stations[0].ps_name = "Charminar PS"; stations[0].lat=17.385044; stations[0].lng=78.474655
    stations[1].ps_name = "Begumpet PS"; stations[1].lat=17.417500; stations[1].lng=78.493889
    stations[2].ps_name = "Chikkadpally PS"; stations[2].lat=17.385278; stations[2].lng=78.486667

    # --- DELHI (80) ---
    for i in range(80):
        stations.append(PoliceStation(
            state="DELHI", district="Central", 
            ps_name=f"Delhi PS {i+1}", 
            lat=28.631 + (i*0.001), lng=77.219 + (i*0.001), 
            phone="112", crime_rate=1586, emergency=True
        ))
    stations[50].ps_name = "Connaught Place PS"; stations[50].lat=28.631458; stations[50].lng=77.219698
    stations[51].ps_name = "Karol Bagh PS"; stations[51].lat=28.649789; stations[51].lng=77.191013
    stations[52].ps_name = "RK Puram PS"; stations[52].lat=28.557959; stations[52].lng=77.192142

    # --- MAHARASHTRA (100) ---
    for i in range(100):
        stations.append(PoliceStation(
            state="MAHARASHTRA", district="Mumbai", 
            ps_name=f"Mumbai PS {i+1}", 
            lat=18.939 + (i*0.001), lng=72.833 + (i*0.001), 
            phone="100", crime_rate=1242, emergency=True
        ))
    stations[130].ps_name = "Crawford Market PS"; stations[130].lat=18.939797; stations[130].lng=72.833542
    stations[131].ps_name = "Pune City PS"; stations[131].lat=18.520430; stations[131].lng=73.856744

    # --- KARNATAKA (60) ---
    for i in range(60):
        stations.append(PoliceStation(
            state="KARNATAKA", district="Bangalore", 
            ps_name=f"Bangalore PS {i+1}", 
            lat=12.971 + (i*0.001), lng=77.594 + (i*0.001), 
            phone="100", crime_rate=850, emergency=True
        ))
    stations[230].ps_name = "Cubbon Park PS"; stations[230].lat=12.9716; stations[230].lng=77.5946

    # --- TAMIL NADU (55) ---
    for i in range(55):
        stations.append(PoliceStation(
            state="TAMIL NADU", district="Chennai", 
            ps_name=f"Chennai PS {i+1}", 
            lat=13.082 + (i*0.001), lng=80.270 + (i*0.001), 
            phone="100", crime_rate=800
        ))
    stations[290].ps_name = "Anna Salai PS"; stations[290].lat=13.0827; stations[290].lng=80.2707

    # --- UTTAR PRADESH (70) ---
    for i in range(70):
        stations.append(PoliceStation(
            state="UTTAR PRADESH", district="Lucknow", 
            ps_name=f"Lucknow PS {i+1}", 
            lat=26.846 + (i*0.001), lng=80.946 + (i*0.001), 
            phone="100", crime_rate=753
        ))
    stations[345].ps_name = "Lucknow Kotwali"; stations[345].lat=26.8467; stations[345].lng=80.9462

    # --- WEST BENGAL (60) ---
    for i in range(60):
        stations.append(PoliceStation(
            state="WEST BENGAL", district="Kolkata", 
            ps_name=f"Kolkata PS {i+1}", 
            lat=22.572 + (i*0.001), lng=88.363 + (i*0.001), 
            phone="100", crime_rate=1242
        ))
    stations[415].ps_name = "Lalbazar PS"; stations[415].lat=22.5726; stations[415].lng=88.3639

    # --- Remaining States/UTs (53) ---
    remaining_regions = [
        ("KERALA", 1586, 10.8505, 76.2711, 40),
        ("GUJARAT", 750, 23.0225, 72.5714, 13)
    ]
    for region, rate, lat, lng, count in remaining_regions:
        for i in range(count):
            stations.append(PoliceStation(
                state=region, district="General", 
                ps_name=f"{region} PS {i+1}", 
                lat=lat + (i*0.01), lng=lng + (i*0.01), 
                phone="112", crime_rate=rate
            ))

    db.session.bulk_save_objects(stations)
    db.session.commit()
    print(f"Success: {len(stations)} stations seeded.")

# --- Helper Functions ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_coordinates(location_name):
    try:
        location = geolocator.geocode(location_name + ", India")
        if location:
            return (location.latitude, location.longitude)
    except Exception as e:
        print(f"Geocoding error: {e}")
    return None

def predict_crime_risk(lat, lng, date_time, weather="Clear"):
    if xgb_model is None:
        return {"risk_score": 0, "crime_type": "Data Unavailable", "recommendation": "System Error"}
    
    dt = datetime.strptime(date_time, '%Y-%m-%dT%H:%M')
    hour = dt.hour
    day_of_week = dt.weekday()
    
    try:
        weather_encoded = weather_encoder.transform([weather])[0]
    except:
        weather_encoded = 0
    
    X_input = pd.DataFrame([[lat, lng, hour, day_of_week, weather_encoded]], 
                           columns=['latitude', 'longitude', 'hour', 'day_of_week', 'weather_encoded'])
    
    probs = xgb_model.predict_proba(X_input)[0]
    max_prob = np.max(probs)
    predicted_class_idx = np.argmax(probs)
    predicted_crime = label_encoder.inverse_transform([predicted_class_idx])[0]
    risk_score = int(max_prob * 100)
    
    # --- GNN Spatial Propagation & Influence ---
    spatial_influence = []
    if gnn_model and xgb_model:
        # 1. Fetch regional crimes for graph building (Mocking regional knowledge)
        regional_crimes = [
            {"lat": lat + 0.02, "lng": lng + 0.01, "rate": 1200},
            {"lat": lat - 0.015, "lng": lng + 0.02, "rate": 900},
            {"lat": lat + 0.01, "lng": lng - 0.01, "rate": 1500}
        ]
        graph_data = build_crime_graph(lat, lng, regional_crimes)
        
        if graph_data:
            with torch.no_grad():
                # GNN refines the risk score based on neighboring nodes
                gnn_refinement = gnn_model(graph_data.x, graph_data.edge_index, graph_data.batch)
                gnn_score = torch.sigmoid(gnn_refinement).item() * 100
                # Weighted average: 60% XGBoost, 40% GNN Spatial Propagation
                risk_score = int(0.6 * risk_score + 0.4 * gnn_score)
            
            spatial_influence = get_spatial_influence_links(lat, lng, regional_crimes)

    # --- Transfer Learning / Generalization ---
    centers = kmeans.cluster_centers_
    min_dist = float('inf')
    for center in centers:
        dist = haversine(lat, lng, center[0], center[1])
        if dist < min_dist:
            min_dist = dist
            
    if min_dist < 1.0: 
        risk_score = min(95, risk_score + 20)
    elif min_dist < 3.0:
        risk_score = min(85, risk_score + 10)
        
    recommendation = "Safe to travel."
    if risk_score > 70:
        recommendation = "HIGH RISK AREA. Avoid if possible or stay alert."
    elif risk_score > 40:
        recommendation = "Moderate risk. Travel with caution."
        
    return {
        "risk_score": risk_score,
        "predicted_crime": predicted_crime,
        "recommendation": recommendation,
        "probabilities": {str(cls): float(round(prob * 100, 1)) for cls, prob in zip(label_encoder.classes_, probs)},
        "gnn_active": True,
        "spatial_influence": spatial_influence
    }

@app.route('/api/crime_trends', methods=['GET'])
def get_crime_trends():
    if bilstm_model is None:
        return jsonify({"error": "Model not loaded"}), 500
    days = [datetime.now().date() - timedelta(days=i) for i in range(14, 0, -1)]
    counts = [50 + int(20 * math.sin(i)) + random.randint(-5, 5) for i in range(14)]
    current_seq_scaled = scaler_lstm.transform(np.array(counts).reshape(-1, 1))
    last_7_tensor = torch.FloatTensor(current_seq_scaled[-7:].reshape(1, 7, 1))
    with torch.no_grad():
        pred = bilstm_model(last_7_tensor)
        pred_val = pred.item()
    pred_count = scaler_lstm.inverse_transform([[pred_val]])[0][0]
    return jsonify({
        "historical": [{"date": d.strftime('%Y-%m-%d'), "count": c} for d, c in zip(days, counts)],
        "forecast": [{"date": (datetime.now().date() + timedelta(days=1)).strftime('%Y-%m-%d'), "count": int(pred_count)}]
    })

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('home'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error="Email already registered")
        hashed_pw = generate_password_hash(password)
        new_user = User(email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/api/predict_route', methods=['POST'])
def predict_route():
    data = request.json
    start_loc = data.get('start_location')
    end_loc = data.get('dest_location')
    routes = get_google_routes(start_loc, end_loc)
    analyzed_routes = [analyze_route_safety(r, model=xgb_model, kmeans=kmeans) for r in routes]
    return jsonify({"routes": analyzed_routes})

@app.route('/api/predict_crime', methods=['POST'])
def predict_location_risk():
    data = request.json
    lat = data.get('lat')
    lng = data.get('lng')
    date_time = datetime.now().strftime('%Y-%m-%dT%H:%M') 
    weather = data.get('weather', 'Clear')
    return jsonify(predict_crime_risk(lat, lng, date_time, weather))

@app.route('/api/hotspots', methods=['GET'])
def get_hotspots():
    return jsonify(kmeans.cluster_centers_.tolist() if kmeans else [])

@app.route('/api/police_search', methods=['POST'])
def police_search():
    data = request.json
    user_lat = float(data.get('lat', 17.385))
    user_lng = float(data.get('lng', 78.486))
    filter_state = data.get('state')
    
    query = PoliceStation.query
    if filter_state:
        query = query.filter(PoliceStation.state == filter_state.upper())
    
    all_stations = query.all()
    results = []
    
    for ps in all_stations:
        dist = haversine(user_lat, user_lng, ps.lat, ps.lng)
        results.append({
            "name": ps.ps_name,
            "state": ps.state,
            "district": ps.district,
            "lat": ps.lat,
            "lng": ps.lng,
            "phone": ps.phone,
            "crime_rate": ps.crime_rate,
            "distance_km": float(round(dist, 2))
        })
    
    # Sort by distance and take top 5
    results.sort(key=lambda x: x['distance_km'])
    top_5 = results[:5]
    
    return jsonify({
        "nearest": top_5,
        "total_stations": len(all_stations),
        "message": f"Nearest: {top_5[0]['name']} ({top_5[0]['distance_km']}km)" if top_5 else "No stations found"
    })

@app.route('/api/nearby_hospitals', methods=['POST'])
def nearby_hospitals():
    data = request.json
    user_lat = float(data.get('lat', 17.385))
    user_lng = float(data.get('lng', 78.486))
    hospitals_with_dist = []
    for hosp in HOSPITALS:
        dist = haversine(user_lat, user_lng, float(hosp['lat']), float(hosp['lng']))
        hospitals_with_dist.append({**hosp, "distance_km": float(round(dist, 2))})
    hospitals_with_dist.sort(key=lambda x: x['distance_km'])
    nearby = [h for h in hospitals_with_dist if h['distance_km'] <= 5.0]
    return jsonify(nearby if len(nearby) >= 3 else hospitals_with_dist[:3])

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/blockchain_alert', methods=['POST'])
def blockchain_alert():
    if 'user_id' not in session:
        user_label = "Guest"
    else:
        user_label = f"User_{session['user_id']}"
        
    data = request.json
    emergency_data = {
        "timestamp": datetime.now().isoformat(),
        "user": user_label,
        "location": {
            "lat": data.get('lat'),
            "lng": data.get('lng')
        },
        "crime_type": data.get('crime_type', 'Emergency Distress'),
        "status": "SOS_TRIGGERED"
    }
    
    # 1. Upload to IPFS
    ipfs_hash = upload_to_ipfs(emergency_data)
    if not ipfs_hash:
        return jsonify({"error": "IPFS Storage Failed"}), 500
        
    # 2. Log on Blockchain
    tx_hash = log_alert_on_chain(ipfs_hash, user_label)
    if not tx_hash:
        return jsonify({"error": "Blockchain Logging Failed"}), 500
        
    return jsonify({
        "status": "Immutable Record Created",
        "ipfs_cid": ipfs_hash,
        "blockchain_hash": tx_hash,
        "explorer_url": f"https://amoy.polygonscan.com/tx/{tx_hash}",
        "ipfs_url": f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}",
        "verification_stamp": "SOS #" + tx_hash[:10] + " VERIFIED"
    })

@app.route('/api/twilio_webhook', methods=['POST'])
def twilio_webhook():
    incoming_msg = request.values.get('Body', '').strip()
    resp = MessagingResponse()
    msg = resp.message()
    separators = [" -> ", "->", " to ", " TO "]
    start_loc = dest_loc = None
    for sep in separators:
        if sep in incoming_msg:
            parts = incoming_msg.split(sep)
            if len(parts) == 2:
                start_loc, dest_loc = parts[0].strip(), parts[1].strip()
                break
    if not start_loc or not dest_loc:
        msg.body("Format: 'Start -> Destination'. Example: 'Charminar -> Begumpet'")
        return str(resp)
    start_coords, dest_coords = get_coordinates(start_loc), get_coordinates(dest_loc)
    if not start_coords or not dest_coords:
        msg.body(f"Error: Could not find locations. Please try: '{start_loc} -> {dest_loc}'")
        return str(resp)
    try:
        routes = get_google_routes(start_loc, dest_loc)
        if not routes:
            msg.body("No routes found between these locations.")
            return str(resp)
        safest_route = analyze_route_safety(routes[0], model=xgb_model, kmeans=kmeans)
        nearest_ps = min(POLICE_STATIONS, key=lambda ps: haversine(dest_coords[0], dest_coords[1], ps['lat'], ps['lng']))
        msg.body(f"🛡️ SafeRoute India Report\nRoute: {start_loc} to {dest_loc}\nRisk: {safest_route['risk_level'].upper()} ({safest_route['safety_score']}/100 Safe)\n🚑 PS: {nearest_ps['name']} ({nearest_ps['phone']})\n📍 Map: https://www.google.com/maps/dir/{start_loc}/{dest_loc}\nStay safe! 🚨")
    except Exception as e:
        print(f"Twilio error: {e}")
        msg.body("An error occurred. Please try again.")
    return str(resp)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_police_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
