"""
Regla 15: Alerta Directa del Agente (Agent Direct Alert)
Técnica MITRE: T1000 (Generico - Bloqueo en Endpoint)
Condición: El agente detectó o bloqueó una amenaza directamente.
"""

RULE_NAME = "ENDPOINT_DIRECT_BLOCK"
MITRE_ID = "T1000"

AGENT_ALERT_EVENTS = {
    "malicious_process_detected",
    "malicious_process_killed",
    "universal_tab_killer",
    "ransomware_canary_modified",
    "malicious_download_blocked",
    "wifi_insecure_network"
}

def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()

    if event_type in AGENT_ALERT_EVENTS:
        severity = event.get("severity", "CRITICAL").upper()
        message = event.get("message", f"El agente bloqueó una amenaza: {event_type}")
        
        return {
            "rule": RULE_NAME,
            "mitre": MITRE_ID,
            "severity": severity,
            "reason": message,
            "src_ip": event.get("src_ip", "UNKNOWN"),
            "event_type": event_type
        }
    return None
