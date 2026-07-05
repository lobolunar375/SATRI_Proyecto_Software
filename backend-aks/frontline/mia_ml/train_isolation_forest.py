import json
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

def train_model(dataset):
    # Features: hour_of_day, day_of_week, country_code, session_duration, action_frequency
    X = []
    y_true = [] # Solo para validación, no se usa en entrenamiento
    for log in dataset:
        X.append([
            log["hour_of_day"],
            log["day_of_week"],
            log["country_code"],
            log["session_duration"],
            log["action_frequency"]
        ])
        y_true.append(1 if log["is_anomaly"] else 0)
        
    X = np.array(X)
    
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X)
    
    # Validación simple
    predictions = model.predict(X)
    # IsolationForest devuelve -1 para anomalía, 1 para normal
    anomalies_detected = sum(1 for p in predictions if p == -1)
    print(f"Anomalías detectadas: {anomalies_detected} (esperadas ~ {sum(y_true)})")
    
    return model

def save_model(model, path="model.joblib"):
    joblib.dump(model, path)
    print(f"Modelo guardado en {path}")

if __name__ == "__main__":
    with open("synthetic_dataset.json", "r") as f:
        dataset = json.load(f)
    model = train_model(dataset)
    save_model(model)
