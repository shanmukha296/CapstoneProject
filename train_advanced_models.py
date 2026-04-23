import pandas as pd
import numpy as np
import xgboost as xgb
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
import joblib
import os
import random
from datetime import datetime, timedelta
from model_definitions import BiLSTM

# --- Configuration ---
MODELS_DIR = 'models'
DATA_PATH = 'data/crimes.csv'
os.makedirs(MODELS_DIR, exist_ok=True)

# --- Feature Engineering & Simulation ---
def add_simulated_weather(df):
    """
    Simulate weather data based on crime type correlation.
    Rainy -> Higher chance of Theft/Burglary (simulated logic)
    """
    weather_types = ['Clear', 'Cloudy', 'Rainy', 'Stormy']
    weights = [0.6, 0.2, 0.15, 0.05] # Probability distribution
    
    # Assign random weather first
    df['weather'] = np.random.choice(weather_types, size=len(df), p=weights)
    
    # Adjust: If crime is Theft, increase chance it was Rainy (simulation)
    mask = df['crime_type'].isin(['Theft', 'Burglary'])
    df.loc[mask, 'weather'] = np.random.choice(weather_types, size=mask.sum(), p=[0.4, 0.2, 0.3, 0.1])
    
    return df

def preprocess_data(df):
    print("Preprocessing data...")
    # DateTime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek # 0=Monday
    
    # Encode Categorical
    le_crime = LabelEncoder()
    df['crime_type_encoded'] = le_crime.fit_transform(df['crime_type'])
    joblib.dump(le_crime, os.path.join(MODELS_DIR, 'label_encoder.pkl'))
    
    le_weather = LabelEncoder()
    df['weather_encoded'] = le_weather.fit_transform(df['weather'])
    joblib.dump(le_weather, os.path.join(MODELS_DIR, 'weather_encoder.pkl'))
    
    return df, le_crime, le_weather

# --- Model 1: XGBoost Classifier ---
def train_xgboost(df):
    print("\nTRAINING XGBOOST...")
    features = ['latitude', 'longitude', 'hour', 'day_of_week', 'weather_encoded']
    target = 'crime_type_encoded'
    
    X = df[features]
    y = df[target]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = xgb.XGBClassifier(
        objective='multi:softprob',
        n_estimators=200,
        learning_rate=0.1,
        max_depth=6,
        use_label_encoder=False,
        eval_metric='mlogloss'
    )
    
    model.fit(X_train, y_train)
    
    acc = model.score(X_test, y_test)
    print(f"XGBoost Accuracy: {acc:.4f}")
    
    joblib.dump(model, os.path.join(MODELS_DIR, 'xgboost_model.pkl'))
    return model

# --- Model 2: BiLSTM for Trend Prediction ---
class CrimeTimeSeriesDataset(Dataset):
    def __init__(self, sequences, targets):
        self.sequences = sequences
        self.targets = targets
        
    def __len__(self):
        return len(self.sequences)
    
    def __getitem__(self, idx):
        return torch.FloatTensor(self.sequences[idx]), torch.FloatTensor([self.targets[idx]])


def create_sequences(data, seq_length):
    xs, ys = [], []
    for i in range(len(data) - seq_length):
        x = data[i:(i+seq_length)]
        y = data[i+seq_length]
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)

def train_bilstm(df):
    print("\nTRAINING BILSTM (TREND PREDICTION)...")
    # Aggregate daily crimes
    daily_crimes = df.groupby('date').size().reset_index(name='count')
    # Ensure all dates are present
    idx = pd.date_range(start=daily_crimes['date'].min(), end=daily_crimes['date'].max())
    daily_crimes.set_index('date', inplace=True)
    daily_crimes = daily_crimes.reindex(idx, fill_value=0).reset_index()
    daily_crimes.rename(columns={'index': 'date'}, inplace=True)
    
    data = daily_crimes['count'].values.reshape(-1, 1)
    
    # Scaling
    scaler = MinMaxScaler()
    data_scaled = scaler.fit_transform(data)
    joblib.dump(scaler, os.path.join(MODELS_DIR, 'scaler_lstm.pkl'))
    
    # Create sequences
    SEQ_LENGTH = 7 # Use past 7 days to predict next day
    X, y = create_sequences(data_scaled, SEQ_LENGTH)
    
    if len(X) == 0:
        print("Not enough data for LSTM training. Skipping.")
        return None

    # Train/Test Split
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    train_dataset = CrimeTimeSeriesDataset(X_train, y_train)
    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    
    # Model Setup
    input_size = 1
    hidden_size = 50
    num_layers = 1
    output_size = 1
    
    model = BiLSTM(input_size, hidden_size, num_layers, output_size)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    
    # Training Loop
    epochs = 100
    for epoch in range(epochs):
        model.train()
        for seqs, targets in train_loader:
            optimizer.zero_grad()
            outputs = model(seqs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
        if (epoch+1) % 10 == 0:
            print(f'Epoch [{epoch+1}/{epochs}], Loss: {loss.item():.4f}')
            
    # Save Model
    torch.save(model.state_dict(), os.path.join(MODELS_DIR, 'bilstm_model.pth'))
    print("BiLSTM Model Saved.")
    return model

# --- Main Execution ---
if __name__ == "__main__":
    print("Loading Data...")
    if not os.path.exists(DATA_PATH):
        print(f"Error: {DATA_PATH} not found.")
        exit()
        
    df = pd.read_csv(DATA_PATH)
    
    # 1. Simulate Weather
    df = add_simulated_weather(df)
    
    # 2. Preprocess
    df, _, _ = preprocess_data(df)
    
    # 3. Train XGBoost
    train_xgboost(df)
    
    # 4. Train BiLSTM
    train_bilstm(df)
    
    print("\nAll models trained and saved successfully.")
