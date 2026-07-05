import requests
import json
import logging
from device_identity import get_device_identity

logger = logging.getLogger("reporter")

class Reporter:
    def __init__(self):
        self.device_id = get_device_identity()
        self.telemetry_url = "http://localhost:8000/api/v1/ingest-log"
        self.heartbeat_url = "http://localhost:8005/api/v1/devices/heartbeat"

    def send_event(self, event_type: str, message: str, severity: str = "INFO", artifacts: dict = None):
        import socket
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except:
            ip = "Unknown"
        payload = {
            "source": self.device_id,
            "event_type": event_type,
            "message": message,
            "src_ip": ip
        }
        try:
            requests.post(self.telemetry_url, json=payload, timeout=5)
            logger.info(f"Evento {event_type} reportado directo a MML.")
        except Exception as e:
            logger.error(f"Fallo al reportar evento: {e}")

    def send_heartbeat(self):
        payload = {
            "device_id": self.device_id,
            "os_version": "Windows 11",
            "agent_version": "1.0.0"
        }
        try:
            requests.post(self.heartbeat_url, json=payload, timeout=5)
        except Exception as e:
            pass

reporter = Reporter()
