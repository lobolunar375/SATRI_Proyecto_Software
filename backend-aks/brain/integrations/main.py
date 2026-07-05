from fastapi import FastAPI, BackgroundTasks
from loguru import logger
from pydantic import BaseModel
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from kafka import KafkaConsumer
import json
import os
import asyncio

from engine import SOAREngine, pending_approvals
from notifier import notify_critical_alert
from report_generator import generate_pdf_report

app = FastAPI(title="SATRI - SOAR Engine v2.0")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

# Inicializamos el motor de Playbooks
engine = SOAREngine()

# ─────────────────────────────────────────
# Modelos de datos
# ─────────────────────────────────────────
class AlertData(BaseModel):
    alert_id: str
    severity: str
    priority: str
    rule_name: str = "UNKNOWN"
    src_ip: str = "0.0.0.0"

# ─────────────────────────────────────────
# Kafka Consumer → Auto-trigger de Playbooks
# ─────────────────────────────────────────
def run_soar_consumer():
    """Consume alertas del topic de triage y dispara playbooks automáticamente."""
    import time
    logger.info("[SOAR] Iniciando Kafka Consumer automático en satri.incidents.triage...")
    
    consumer = None
    for attempt in range(30):
        try:
            consumer = KafkaConsumer(
                "satri.incidents.triage",
                bootstrap_servers=KAFKA_BROKER,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                group_id="soar-engine-group"
            )
            logger.success(f"[SOAR] Conectado a Kafka en intento {attempt + 1}")
            break
        except Exception as e:
            logger.warning(f"[SOAR] Kafka no disponible (intento {attempt + 1}/30): {e}")
            time.sleep(5)

    if consumer is None:
        logger.error("[SOAR] No se pudo conectar a Kafka después de 30 intentos")
        return

    # Crear un nuevo event loop para este hilo
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for message in consumer:
        alert = message.value
        alert_id = alert.get("alert_id") or alert.get("incident_id", "UNKNOWN")
        severity = alert.get("severity", "MEDIUM")
        rule = alert.get("correlation_rule") or alert.get("rule_name", "UNKNOWN")
        src_ip = alert.get("src_ip", "N/A")
        
        logger.info(f"[SOAR] 📥 Alerta recibida de Kafka: {alert_id} | {severity} | {rule}")
        
        # Construir datos para el motor
        soar_data = {
            "alert_id": alert_id,
            "severity": severity,
            "rule_name": rule,
            "correlation_rule": rule,
            "src_ip": src_ip,
            "priority": alert.get("priority", "P3"),
            **alert  # Pasar todos los campos originales
        }
        
        # Ejecutar el motor de playbooks
        try:
            result = loop.run_until_complete(engine.execute(soar_data))
            if result.get("status") == "executed":
                logger.success(f"[SOAR] ✅ Playbooks ejecutados para {alert_id}")
            else:
                logger.debug(f"[SOAR] Sin match para {alert_id}")
        except Exception as e:
            logger.error(f"[SOAR] Error ejecutando playbooks: {e}")

# ─────────────────────────────────────────
# REST API Endpoints
# ─────────────────────────────────────────
@app.post("/ticket")
async def create_ticket(data: AlertData):
    ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d')}-{data.alert_id[-4:]}"
    logger.warning(f"[JIRA] Ticket creado: {ticket_id} | Prioridad: {data.priority}")
    return {"status": "success", "ticket_id": ticket_id}

@app.post("/api/v1/notify")
async def handle_notification(alert: dict):
    """Endpoint llamado por el MTA cuando una alerta es CRITICAL o bloqueada."""
    logger.info(f"[SOAR] Recibida solicitud de notificación para {alert.get('alert_id')}")
    
    # 1. Notificar a Webhooks
    notify_critical_alert(alert)
    
    # 2. Generar Reporte PDF
    pdf_path = generate_pdf_report(alert)
    
    return {
        "status": "success",
        "notified": True,
        "pdf_report": pdf_path
    }

@app.post("/soar")
async def execute_soar(data: AlertData, background_tasks: BackgroundTasks):
    """
    Endpoint manual del SOAR (llamado por el Dashboard o MTA).
    """
    alert_dict = data.dict()
    logger.info(f"[SOAR] Evaluando alerta manual: {data.alert_id} ({data.severity})")
    background_tasks.add_task(engine.execute, alert_dict)
    return {"status": "success", "message": "SOAR Playbooks evaluation started"}

# ─────────────────────────────────────────
# Human-in-the-Loop: Aprobaciones
# ─────────────────────────────────────────
@app.get("/api/approvals")
async def list_approvals():
    """Lista todas las acciones pendientes de aprobación."""
    items = []
    for aid, data in pending_approvals.items():
        items.append({
            "approval_id": aid,
            "action_type": data.get("action_type"),
            "src_ip": data.get("src_ip"),
            "severity": data.get("severity"),
            "playbook": data.get("playbook_name"),
            "status": data.get("status"),
            "created_at": data.get("created_at"),
        })
    # Pendientes primero
    items.sort(key=lambda x: (0 if x["status"] == "PENDING" else 1, x["created_at"]), reverse=True)
    return {"approvals": items, "pending_count": sum(1 for i in items if i["status"] == "PENDING")}

@app.post("/api/approvals/{approval_id}/approve")
async def approve_action(approval_id: str):
    """Un analista SOC aprueba la acción destructiva."""
    result = await engine.approve(approval_id)
    return result

@app.post("/api/approvals/{approval_id}/reject")
async def reject_action(approval_id: str):
    """Un analista SOC rechaza la acción destructiva."""
    result = await engine.reject(approval_id)
    return result

# ─────────────────────────────────────────
# Historial de ejecuciones
# ─────────────────────────────────────────
@app.get("/api/soar/history")
async def soar_history():
    """Historial de playbooks ejecutados."""
    return {"executions": engine.execution_log[-20:]}

# ─────────────────────────────────────────
# Health & Startup
# ─────────────────────────────────────────
@app.get("/health")
async def health():
    pending_count = sum(1 for v in pending_approvals.values() if v["status"] == "PENDING")
    return {
        "status": "ok", 
        "service": "soar-engine-v2",
        "loaded_playbooks": len(engine.playbooks),
        "pending_approvals": pending_count
    }

@app.on_event("startup")
async def startup():
    loop = asyncio.get_event_loop()
    loop.run_in_executor(ThreadPoolExecutor(max_workers=1), run_soar_consumer)
    logger.success("[SOAR] Motor SOAR v2.0 iniciado con Kafka Consumer automático")
