import numpy as np
import hashlib
from datetime import datetime
from sklearn.ensemble import IsolationForest
from loguru import logger

class UEBAModel:
    def __init__(self, contamination=0.05):
        """
        contamination: Proporción estimada de anomalías en los datos (5% por defecto).
        """
        self.model = IsolationForest(
            n_estimators=100, 
            contamination=contamination,
            random_state=42
        )
        self.is_trained = False
        
    def _extract_features(self, log_data):
        """
        Convierte un log crudo JSON en un vector numérico (Feature Engineering).
        """
        # 1. Longitud del mensaje
        msg = log_data.get("message", "")
        msg_len = len(msg)
        
        # 2. Hora del día (0-23)
        try:
            ts_str = log_data.get("timestamp", "")
            if ts_str:
                # ISO format parse
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                hour = dt.hour
            else:
                hour = 12
        except:
            hour = 12
            
        # 3. Tipo de evento (Hash encoding)
        ev_type = log_data.get("event_type", "unknown")
        # Un hash simple modulado a 10 clases para que no explote la dimensionalidad
        ev_hash = int(hashlib.md5(ev_type.encode()).hexdigest(), 16) % 10
        
        # 4. Indicadores de severidad basados en texto
        is_blocked = 1 if "block" in msg.lower() or "kill" in msg.lower() else 0
        
        # Vector: [Hora, Longitud, TipoEvento, Bloqueado]
        return [hour, msg_len, ev_hash, is_blocked]

    def train(self, historical_logs):
        """
        Entrena (fit) el modelo de Isolation Forest con un lote de logs.
        """
        logger.info(f"[MIA-ML] Extrayendo características de {len(historical_logs)} logs para entrenamiento...")
        X = [self._extract_features(log) for log in historical_logs]
        X = np.array(X)
        
        logger.info("[MIA-ML] Entrenando modelo Isolation Forest...")
        self.model.fit(X)
        self.is_trained = True
        logger.success("[MIA-ML] Entrenamiento completado.")

    def initialize_with_synthetic_data(self):
        """
        Sin datos históricos reales, el modelo no se puede entrenar.
        Se esperará a recibir logs reales para establecer la línea base.
        """
        logger.warning("[MIA-ML] Sin datos históricos. El modelo esperará logs reales para entrenarse.")

    def predict(self, log_data):
        """
        Evalúa un log individual.
        Devuelve (is_anomaly: bool, anomaly_score: float)
        Score < 0 es Anomalía.
        """
        if not self.is_trained:
            logger.warning("[MIA-ML] El modelo no está entrenado. Ignorando evaluación.")
            return False, 0.0
            
        x = self._extract_features(log_data)
        X = np.array([x])
        
        # predict() devuelve -1 para anomalía (outlier) y 1 para inlier
        prediction = self.model.predict(X)[0]
        
        # decision_function() devuelve un score continuo. 
        # Valores negativos = outliers. Valores grandes = inliers.
        score = self.model.decision_function(X)[0]
        
        is_anomaly = (prediction == -1)
        
        return is_anomaly, score
