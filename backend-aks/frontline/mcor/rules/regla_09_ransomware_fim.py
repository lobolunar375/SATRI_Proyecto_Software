"""
Regla 09: Comportamiento de ransomware (FIM)
Técnica MITRE: T1486 (Data Encrypted for Impact)
Condición: >= 10 archivos renombrados/modificados con extensiones sospechosas en 1 min
"""
from time_window_engine import increment_counter

RULE_NAME = "RANSOMWARE_FIM"
MITRE_ID = "T1486"
THRESHOLD = 10
WINDOW_SECONDS = 60

RANSOMWARE_EXTENSIONS = {
    ".locked", ".encrypted", ".cry", ".crypt", ".enc",
    ".locky", ".cerber", ".zepto", ".wnry", ".wncry"
}


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()

    if event_type not in ["file_rename", "file_modify", "ransomware_block", "ransomware_behavior_detected"]:
        return None

    resource = event.get("resource_name", event.get("file_name", "")).lower()
    src_ip = event.get("src_ip", "local")

    is_ransomware_ext = any(resource.endswith(ext) for ext in RANSOMWARE_EXTENSIONS)
    is_ransomware_event = "ransomware" in event_type

    if is_ransomware_ext or is_ransomware_event:
        key = f"mcor:r09:ransom:{src_ip}"
        count = increment_counter(key, WINDOW_SECONDS)

        if count >= THRESHOLD or is_ransomware_event:
            return {
                "rule": RULE_NAME,
                "mitre": MITRE_ID,
                "severity": "CRITICAL",
                "reason": f"Comportamiento RANSOMWARE: {count} archivos modificados con extensión sospechosa desde {src_ip}",
                "src_ip": src_ip,
                "count": count,
                "file": resource
            }
    return None

