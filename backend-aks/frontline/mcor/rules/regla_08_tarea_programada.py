"""
Regla 08: Modificación de tareas programadas
Técnica MITRE: T1053 (Scheduled Task/Job)
Condición: Creación o modificación de tarea programada
"""

RULE_NAME = "SCHEDULED_TASK_MODIFIED"
MITRE_ID = "T1053"


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()
    message = event.get("message", "").lower()

    triggers = ["scheduled_task", "crontab", "schtasks", "at_job", "cron_modify", "task_scheduler"]

    if event_type in triggers or any(t in message for t in triggers):
        return {
            "rule": RULE_NAME,
            "mitre": MITRE_ID,
            "severity": "MEDIUM",
            "reason": f"Modificación de tarea programada detectada desde {event.get('src_ip', 'N/A')}",
            "src_ip": event.get("src_ip"),
            "message": event.get("message", "")[:200]
        }
    return None
