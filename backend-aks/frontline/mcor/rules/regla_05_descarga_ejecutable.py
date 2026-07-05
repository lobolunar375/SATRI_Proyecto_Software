"""
Regla 05: Descarga de archivo ejecutable inusual
Técnica MITRE: T1105 (Ingress Tool Transfer)
Condición: Descarga de .exe/.bat/.ps1/.sh/.msi/.dll desde fuente no confiable
"""

RULE_NAME = "SUSPICIOUS_EXECUTABLE_DOWNLOAD"
MITRE_ID = "T1105"

SUSPICIOUS_EXTENSIONS = {".exe", ".bat", ".ps1", ".sh", ".msi", ".dll", ".scr", ".vbs", ".cmd"}


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()

    if event_type not in ["download", "file_download", "malicious_download_detected"]:
        return None

    resource = event.get("resource_name", event.get("file_name", "")).lower()
    if any(resource.endswith(ext) for ext in SUSPICIOUS_EXTENSIONS):
        return {
            "rule": RULE_NAME,
            "mitre": MITRE_ID,
            "severity": "HIGH",
            "reason": f"Descarga de ejecutable sospechoso: {resource}",
            "src_ip": event.get("src_ip"),
            "file": resource
        }
    return None
