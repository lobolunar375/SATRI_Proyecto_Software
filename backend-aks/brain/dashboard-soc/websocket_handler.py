from fastapi import WebSocket
from typing import List
from loguru import logger
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Cliente conectado al Dashboard. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Cliente desconectado del Dashboard. Total: {len(self.active_connections)}")

    async def broadcast_alert(self, alert_data: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(alert_data))
            except Exception as e:
                logger.error(f"Error enviando WebSocket: {e}")
                self.disconnect(connection)

manager = ConnectionManager()
