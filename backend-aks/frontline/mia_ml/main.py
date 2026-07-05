from fastapi import FastAPI, Request
from pydantic import BaseModel
import joblib
import numpy as np
from loguru import logger
import os

app = FastAPI(title="SATRI - MIA ML (UEBA)", description="Motor de Detección de Anomalías de Comportamiento")

model = None

@app.on_event("startup")
async def startup_event():
    global model
    model_path = os.getenv("MODEL_PATH", "model.joblib")
    if os.path.exists(model_path):
        model = joblib.load(model_path)
        logger.info(f"Modelo cargado desde {model_path}")
    else:
        logger.error(f"No se encontró el modelo en {model_path}. Entrene el modelo offline primero.")

class EventLog(BaseModel):
    hour_of_day: int
    day_of_week: int
    country_code: int
    session_duration: float
    action_frequency: int

@app.post("/score")
async def score_event(event: EventLog):
    if model is None:
        return {"error": "Model not loaded"}
        
    X = np.array([[
        event.hour_of_day,
        event.day_of_week,
        event.country_code,
        event.session_duration,
        event.action_frequency
    ]])
    
    # decision_function devuelve un score continuo. Valores negativos = anomalías.
    score = model.decision_function(X)[0]
    prediction = model.predict(X)[0]
    
    is_anomaly = (prediction == -1)
    
    # Para consistencia con otras herramientas, podemos devolver una puntuación normalizada o mantenerla.
    # Usaremos el score directo, donde score menor indica mayor anomalía.
    return {
        "is_anomaly": bool(is_anomaly),
        "anomaly_score": float(score)
    }

@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": model is not None}

@app.get("/ready")
async def ready():
    return {"status": "ready" if model is not None else "not_ready"}
