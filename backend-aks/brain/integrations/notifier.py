import requests
import os
from loguru import logger

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

def notify_discord(alert: dict):
    if not DISCORD_WEBHOOK_URL:
        logger.warning("[NOTIFIER] Discord Webhook URL no configurada.")
        return
        
    embed = {
        "title": f"🚨 ALERTA CRÍTICA: {alert.get('rule_name', 'UNKNOWN')}",
        "description": alert.get("correlation_reason", "Sin detalles de correlación."),
        "color": 16711680, # Rojo
        "fields": [
            {"name": "Alert ID", "value": alert.get("alert_id", "N/A"), "inline": True},
            {"name": "Severidad", "value": alert.get("severity", "N/A"), "inline": True},
            {"name": "IP Origen", "value": alert.get("src_ip", "N/A"), "inline": True},
            {"name": "Acción MTA", "value": alert.get("triage_decision", "N/A"), "inline": True}
        ]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
        response.raise_for_status()
        logger.info(f"[NOTIFIER] Alerta enviada a Discord: {alert.get('alert_id')}")
    except Exception as e:
        logger.error(f"[NOTIFIER] Error enviando a Discord: {e}")

def notify_slack(alert: dict):
    if not SLACK_WEBHOOK_URL:
        logger.warning("[NOTIFIER] Slack Webhook URL no configurada.")
        return
        
    payload = {
        "text": f"🚨 *ALERTA CRÍTICA: {alert.get('rule_name', 'UNKNOWN')}*\n"
                f"*Alert ID:* {alert.get('alert_id', 'N/A')}\n"
                f"*Severidad:* {alert.get('severity', 'N/A')}\n"
                f"*IP Origen:* {alert.get('src_ip', 'N/A')}\n"
                f"*Detalles:* {alert.get('correlation_reason', 'N/A')}"
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"[NOTIFIER] Alerta enviada a Slack: {alert.get('alert_id')}")
    except Exception as e:
        logger.error(f"[NOTIFIER] Error enviando a Slack: {e}")

def notify_critical_alert(alert: dict):
    notify_discord(alert)
    notify_slack(alert)
