import googlemaps
import polyline
import numpy as np
import pandas as pd
from datetime import datetime
import math
import os
from geopy.geocoders import Nominatim

# Placeholder for API Key - User must replace this!
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', 'YOUR_GOOGLE_MAPS_API_KEY')
geolocator = Nominatim(user_agent="safe_route_india_routing_demo")

def get_google_routes(start, end, departure_time=None):
    """
    Fetches routes from Google Maps API.
    Returns a list of dicts with route details.
    """
    if GOOGLE_MAPS_API_KEY == 'YOUR_GOOGLE_MAPS_API_KEY':
        print("Warning: No Google Maps API Key provided. Using mock data.")
        return get_mock_routes(start, end)
        
    try:
        gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
        
        if departure_time is None:
            departure_time = datetime.now()
            
        directions_result = gmaps.directions(
            start,
            end,
            mode="driving",
            alternatives=True,
            departure_time=departure_time
        )
        
        routes = []
        for i, route in enumerate(directions_result):
            summary = route.get('summary', f'Route {i+1}')
            leg = route['legs'][0]
            duration = leg['duration']['text']
            duration_in_traffic = leg.get('duration_in_traffic', {}).get('text', duration)
            distance = leg['distance']['text']
            
            # Decode polyline
            overview_polyline = route['overview_polyline']['points']
            path = polyline.decode(overview_polyline) # List of (lat, lng) tuples
            
            routes.append({
                "summary": summary,
                "duration": duration,
                "duration_in_traffic": duration_in_traffic,
                "distance": distance,
                "path": path,
                "overview_polyline": overview_polyline
            })
            
        return routes
        
    except Exception as e:
        print(f"Error fetching Google Routes: {e}")
        return get_mock_routes(start, end)

def get_mock_routes(start, end):
    """
    Returns simulated routes for testing/demo without API key.
    Constructs a straight line and a slightly curved line.
    """
    # Try to geocode locations for path generation
    try:
        loc1 = geolocator.geocode(start + ", India")
        loc2 = geolocator.geocode(end + ", India")
        
        if not loc1 or not loc2:
            print("Mock Geocoding failed.")
            return []
            
        p1 = (loc1.latitude, loc1.longitude)
        p2 = (loc2.latitude, loc2.longitude)
        
        # Create a simple 5-point path with a slight curve
        mid_lat = (p1[0] + p2[0]) / 2 + 0.005
        mid_lng = (p1[1] + p2[1]) / 2 + 0.005
        
        path = [
            p1,
            (p1[0]*0.75 + p2[0]*0.25, p1[1]*0.75 + p2[1]*0.25 + 0.002),
            (mid_lat, mid_lng),
            (p1[0]*0.25 + p2[0]*0.75, p1[1]*0.25 + p2[1]*0.75 + 0.002),
            p2
        ]
        
        return [{
            "summary": "Mock Route (via Primary Road)",
            "duration": "25 mins",
            "duration_in_traffic": "32 mins",
            "distance": f"{round(haversine(p1[0], p1[1], p2[0], p2[1]), 1)} km",
            "path": path,
            "overview_polyline": "" # Not used for mock
        }]
    except Exception as e:
        print(f"Mock error: {e}")
        return []

def analyze_route_safety(route, model, scaler_lstm=None, label_encoder=None, weather_encoder=None, kmeans=None):
    """
    Analyzes the safety of a route by sampling points every 100m.
    """
    path = route['path']
    if not path:
        return {**route, "safety_score": 0, "risk_level": "Unknown", "risk_segments": []}
        
    # Interpolate points every 100m
    sampled_points = sample_points(path, interval_meters=100)
    
    risk_segments = []
    total_risk = 0
    
    # Predict risk for each point
    # We need the prediction logic here. Ideally import `predict_crime_risk` from app
    # but to avoid circular imports, we might need to pass the prediction function or logic.
    # For now, let's implement a simplified prediction loop using the passed model.
    
    # We need to reconstruct the feature vector for the model
    # [lat, lng, hour, day, weather]
    dt = datetime.now()
    hour = dt.hour
    day = dt.weekday()
    weather_encoded = 0 # Default clear
    
    for point in sampled_points:
        lat, lng = point
        
        # Prepare input
        X_input = pd.DataFrame([[lat, lng, hour, day, weather_encoded]], 
                               columns=['latitude', 'longitude', 'hour', 'day_of_week', 'weather_encoded'])
        
        # Predict
        try:
            probs = model.predict_proba(X_input)[0]
            risk = int(np.max(probs) * 100)
            
            # Hotspot adjustment (KMeans)
            if kmeans:
                centers = kmeans.cluster_centers_
                min_dist = float('inf')
                for center in centers:
                    dist = haversine(lat, lng, center[0], center[1])
                    if dist < min_dist:
                        min_dist = dist
                if min_dist < 1.0: risk += 20
                elif min_dist < 3.0: risk += 10
            
            risk = min(100, risk)
            
        except Exception as e:
            risk = 50 # Default if error
            
        risk_segments.append({"lat": lat, "lng": lng, "risk": risk})
        total_risk += risk
        
    avg_risk = total_risk / len(sampled_points) if sampled_points else 0
    safety_score = max(0, 100 - avg_risk) # Invert risk to get safety
    
    risk_level = "High"
    if safety_score > 70: risk_level = "Safe"
    elif safety_score > 40: risk_level = "Moderate"
    
    return {
        **route,
        "safety_score": int(safety_score),
        "risk_level": risk_level,
        "risk_segments": risk_segments
    }

def sample_points(path, interval_meters=100):
    """
    Interpolates points along a path at fixed intervals.
    Path is list of (lat, lng).
    """
    sampled = [path[0]]
    for i in range(len(path) - 1):
        p1 = path[i]
        p2 = path[i+1]
        dist = haversine(p1[0], p1[1], p2[0], p2[1]) * 1000 # to meters
        
        if dist > interval_meters:
            num_points = int(dist // interval_meters)
            for j in range(1, num_points + 1):
                frac = j / (num_points + 1)
                lat = p1[0] + (p2[0] - p1[0]) * frac
                lng = p1[1] + (p2[1] - p1[1]) * frac
                sampled.append((lat, lng))
        sampled.append(p2)
    return sampled

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
