"""
Regla 07: Creación de cuenta de usuario nueva
Técnica MITRE: T1136 (Create Account)
Condición: Evento de creación de cuenta local
"""

RULE_NAME = "NEW_ACCOUNT_CREATED"
MITRE_ID = "T1136"


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()
    message = event.get("message", "").lower()

    triggers = ["account_created", "user_add", "useradd", "net user /add", "create_account"]

    if event_type in triggers or any(t in message for t in triggers):
        return {
            "rule": RULE_NAME,
            "mitre": MITRE_ID,
            "severity": "MEDIUM",
            "reason": f"Creación de cuenta nueva detectada desde {event.get('src_ip', 'N/A')}",
            "src_ip": event.get("src_ip"),
            "message": event.get("message", "")[:200]
        }
    return None
