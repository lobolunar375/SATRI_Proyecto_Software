"""
Regla 04: Ejecución de proceso desconocido
Técnica MITRE: T1059 (Command and Scripting Interpreter)
Condición: Proceso no está en whitelist de procesos conocidos
"""

RULE_NAME = "UNKNOWN_PROCESS_EXECUTION"
MITRE_ID = "T1059"

KNOWN_PROCESSES = {
    "explorer.exe", "svchost.exe", "chrome.exe", "firefox.exe",
    "code.exe", "python.exe", "node.exe", "cmd.exe", "powershell.exe",
    "taskmgr.exe", "notepad.exe", "msiexec.exe", "systemd", "bash",
    "sh", "cron", "sshd", "nginx", "apache2", "docker",
}


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()

    if event_type not in ["process_execution", "process_creation"]:
        return None

    process_name = event.get("process_name", "").lower().strip()
    if not process_name:
        return None

    if process_name not in KNOWN_PROCESSES:
        return {
            "rule": RULE_NAME,
            "mitre": MITRE_ID,
            "severity": "MEDIUM",
            "reason": f"Proceso desconocido ejecutado: {process_name}",
            "src_ip": event.get("src_ip"),
            "process": process_name
        }
    return None
