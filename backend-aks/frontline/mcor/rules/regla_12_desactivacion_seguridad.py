"""
Regla 12: Desactivación de antivirus/seguridad
Técnica MITRE: T1562 (Impair Defenses)
Condición: Evento de detención de servicio de seguridad
"""

RULE_NAME = "SECURITY_DISABLED"
MITRE_ID = "T1562"

SECURITY_SERVICES = {
    "windows defender", "windefend", "mpssvc", "firewall",
    "satri", "antivirus", "antimalware", "security_service",
    "tamper_protection", "realtime_protection"
}


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()
    message = event.get("message", "").lower()

    if event_type not in ["service_stop", "security_disable", "defense_impair", "tamper_detected"]:
        return None

    service = event.get("service_name", "").lower()
    is_security = any(s in service or s in message for s in SECURITY_SERVICES)

    if is_security:
        return {
            "rule": RULE_NAME,
            "mitre": MITRE_ID,
            "severity": "CRITICAL",
            "reason": f"Servicio de seguridad desactivado: {service or 'desconocido'} desde {event.get('src_ip', 'local')}",
            "src_ip": event.get("src_ip"),
            "service": service
        }
    return None
