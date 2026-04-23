import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.preprocessing import LabelEncoder
import joblib
import os

# Create models directory if it doesn't exist
if not os.path.exists('models'):
    os.makedirs('models')

print("Loading data...")
try:
    df = pd.read_csv('data/crimes.csv')
except FileNotFoundError:
    print("Error: data/crimes.csv not found.")
    exit()

print("Preprocessing data...")
# Encode crime type
le = LabelEncoder()
df['crime_type_encoded'] = le.fit_transform(df['crime_type'])

# Save label encoder
joblib.dump(le, 'models/label_encoder.pkl')

# Features for prediction: lat, lon, hour, day_of_week
# We need to encode day_of_week
day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}
df['day_encoded'] = df['day_of_week'].map(day_map)

X = df[['latitude', 'longitude', 'hour', 'day_encoded']]
y = df['crime_type_encoded']

print("Training Random Forest Classifier...")
rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
rf_model.fit(X, y)

# Save Random Forest model
joblib.dump(rf_model, 'models/rf_model.pkl')
print(f"Random Forest model accuracy: {rf_model.score(X, y):.2f}")

print("Training K-Means Clustering for Hotspots...")
# Clustering based on location only
X_loc = df[['latitude', 'longitude']]
kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
kmeans.fit(X_loc)

# Save K-Means model
joblib.dump(kmeans, 'models/kmeans_model.pkl')

print("Models saved successfully in 'models/' directory.")
