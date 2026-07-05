from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from aiokafka import AIOKafkaConsumer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
import asyncio
import json
import os
import httpx
from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from auth import create_access_token, verify_token, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta

app = FastAPI(title="SATRI SOC Dashboard", description="API REST y WebSockets para el Centro de Operaciones de Seguridad", version="2.0.0")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://satri:satri2025@mongodb:27017")
INTEGRATIONS_URL = os.getenv("INTEGRATIONS_URL", "http://integrations:8004")

# ──────────────────────────────────────────────
# Gestor de conexiones WebSocket en tiempo real
# ──────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        # Crear copia de la lista para iterar sin modificarla mientras se lee
        for ws in list(self.active_connections):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()

# ──────────────────────────────────────────────
# MongoDB client (async)
# ──────────────────────────────────────────────
mongo_client: AsyncIOMotorClient = None
db = None

@app.on_event("startup")
async def startup():
    global mongo_client, db
    mongo_client = AsyncIOMotorClient(MONGO_URI)
    db = mongo_client["satri_ioc_db"]
    logger.success("Dashboard SOC conectado a MongoDB")
    # Iniciar tarea de polling en tiempo real
    asyncio.create_task(realtime_alert_poller())
    asyncio.create_task(realtime_raw_logs_consumer())

@app.on_event("shutdown")
async def shutdown():
    if mongo_client:
        mongo_client.close()

# ──────────────────────────────────────────────
# Polling de MongoDB → WebSocket Broadcast
# ──────────────────────────────────────────────
last_seen_alert_id = None

async def realtime_alert_poller():
    """Consulta MongoDB cada 3s y emite nuevas alertas vía WebSocket."""
    global last_seen_alert_id
    from bson.objectid import ObjectId
    
    # 1. Obtener el ID de la alerta más reciente al arrancar para no inundar el frontend
    try:
        if db is not None:
            collection = db["triage_incidents"]
            last_doc = await collection.find_one({}, sort=[("_id", -1)])
            if last_doc:
                last_seen_alert_id = str(last_doc["_id"])
    except Exception:
        pass

    while True:
        try:
            if db is not None:
                collection = db["triage_incidents"]
                query = {}
                if last_seen_alert_id:
                    query["_id"] = {"$gt": ObjectId(last_seen_alert_id)}
                
                # Buscar alertas nuevas ordenadas de la más antigua a la más nueva (entre las nuevas)
                cursor = collection.find(query).sort("_id", 1).limit(50)
                docs = await cursor.to_list(length=50)
                
                for doc in docs:
                    last_seen_alert_id = str(doc["_id"])
                    doc["_id"] = str(doc["_id"])
                    await manager.broadcast({"type": "new_alert", "data": doc})
        except Exception as e:
            print(f"POLLER ERROR: {e}")
            import traceback
            traceback.print_exc()
        await asyncio.sleep(3)

# ──────────────────────────────────────────────
# Streaming en vivo de Kafka para tráfico crudo
# ──────────────────────────────────────────────
async def realtime_raw_logs_consumer():
    """Consume logs en bruto desde Kafka y los transmite al WebSocket."""
    logger.info("Iniciando consumidor de Kafka para Raw Traffic...")
    KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
    consumer = AIOKafkaConsumer(
        "satri.logs.raw",
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        group_id="dashboard-raw-logs",
        auto_offset_reset="latest"  # Solo tráfico nuevo
    )
    
    for attempt in range(15):
        try:
            await consumer.start()
            logger.success("Consumidor de Raw Logs conectado a Kafka")
            break
        except Exception as e:
            await asyncio.sleep(5)
    
    while True:
        try:
            async for msg in consumer:
                log = msg.value
                try:
                    await manager.broadcast({"type": "raw_log", "data": log})
                except Exception as e:
                    logger.error(f"Error enviando broadcast: {e}")
        except Exception as e:
            logger.error(f"Error en raw logs consumer (reconectando en 5s): {e}")
            await asyncio.sleep(5)
    
    # En caso de que se necesite cerrar (nunca debería llegar aquí normalmente)
    await consumer.stop()

# ──────────────────────────────────────────────
# API REST - Datos para el Dashboard
# ──────────────────────────────────────────────
@app.post("/api/auth/login", tags=["Auth"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # Mock authentication para FASE 7 (en un entorno real iría a BD o AD)
    if form_data.username == "admin" and form_data.password == "satri2025":
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": form_data.username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Usuario o contraseña incorrectos",
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.get("/api/raw-logs", tags=["Data"])
async def get_raw_logs(limit: int = 100, current_user: str = Depends(verify_token)):
    """Retorna los últimos logs en bruto de la colección triage_incidents para el Data Lake."""
    try:
        col = db["triage_incidents"]
        projection = {
            "_id": 0, "src_ip": 1, "event_type": 1, "rule_name": 1,
            "severity": 1, "timestamp": 1, "triage_decision": 1,
            "correlation_id": 1, "priority": 1,
            "artifacts": 1, "message": 1,
            # Campos con log_data (documentos más nuevos del agente)
            "log_data": 1
        }
        cursor = col.find({}, projection).sort("_id", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        logs = []
        for doc in docs:
            # Si el doc tiene log_data (formato nuevo), usar eso
            if doc.get("log_data") and isinstance(doc["log_data"], dict):
                logs.append(doc["log_data"])
            else:
                # Formato antiguo: campos en la raíz
                log_entry = {
                    "src_ip": doc.get("src_ip") or doc.get("artifacts", {}).get("src_ip", "N/A"),
                    "event_type": doc.get("event_type", "unknown"),
                    "message": doc.get("rule_name") or doc.get("message", ""),
                    "severity": doc.get("severity", ""),
                    "timestamp": doc.get("timestamp", ""),
                    "triage_decision": doc.get("triage_decision", ""),
                }
                logs.append(log_entry)
        # Retornar del más antiguo al más nuevo
        logs.reverse()
        return {"logs": logs, "count": len(logs)}
    except Exception as e:
        logger.error(f"Error en /api/raw-logs: {e}")
        return {"logs": [], "count": 0}

# ──────────────────────────────────────────────
@app.get("/api/stats", tags=["Dashboard"])
async def get_stats(current_user: str = Depends(verify_token)):
    """Estadísticas generales para las tarjetas del dashboard."""
    try:
        col = db["triage_incidents"]
        total = await col.count_documents({})
        critical = await col.count_documents({"severity": "CRITICAL"})
        high = await col.count_documents({"severity": "HIGH"})
        blocked = await col.count_documents({"triage_decision": "BLOCK"})
        
        # Contar por regla de correlación
        pipeline = [
            {"$group": {"_id": "$correlation_rule", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        rules_cursor = col.aggregate(pipeline)
        rules = await rules_cursor.to_list(length=10)
        
        # ── Fase 4: Detectar agentes con Ring-0 activo ──
        # Los agentes con kernel driver activo emiten un evento kernel_driver_online
        kernel_agents_cursor = col.distinct("log_data.source",
            {"log_data.event_type": "kernel_driver_online"}
        )
        kernel_agents = await kernel_agents_cursor if hasattr(kernel_agents_cursor, '__await__') else []
        kernel_agent_count = 0
        try:
            # Motor de búsqueda alternativo via ioc_intelligence
            raw_col = db["triage_incidents"]
            k_pipeline = [
                {"$match": {"log_data.event_type": "kernel_driver_online"}},
                {"$group": {"_id": "$log_data.src_ip"}},
                {"$count": "total"}
            ]
            k_cur = raw_col.aggregate(k_pipeline)
            k_res = await k_cur.to_list(length=1)
            kernel_agent_count = k_res[0]["total"] if k_res else 0
        except Exception:
            kernel_agent_count = 0
        
        return {
            "total_alerts": total,
            "critical": critical,
            "high": high,
            "blocked": blocked,
            "active_agents": 1,
            "kernel_agents": kernel_agent_count,   # Agentes con Ring-0 activo
            "rules_breakdown": [{"rule": r["_id"] or "UNKNOWN", "count": r["count"]} for r in rules]
        }
    except Exception as e:
        return {"total_alerts": 0, "critical": 0, "high": 0, "blocked": 0,
                "active_agents": 0, "kernel_agents": 0, "rules_breakdown": []}

@app.get("/api/alerts", tags=["Dashboard"])
async def get_alerts(limit: int = 50, severity: str = None, current_user: str = Depends(verify_token)):
    """Lista de alertas recientes."""
    try:
        col = db["triage_incidents"]
        query = {}
        if severity:
            query["severity"] = severity.upper()
        
        cursor = col.find(query).sort("_id", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        
        return {"alerts": docs, "count": len(docs)}
    except Exception as e:
        return {"alerts": [], "count": 0}

@app.get("/api/iocs", tags=["Intelligence"])
async def get_iocs(limit: int = 30, current_user: str = Depends(verify_token)):
    """Top IoCs detectados."""
    try:
        col = db["ioc_intelligence"]
        cursor = col.find({"vt_label": {"$in": ["MALICIOUS", "SUSPICIOUS"]}}).sort("vt_score", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return {"iocs": docs}
    except Exception as e:
        return {"iocs": []}

@app.post("/api/action/isolate/{src_ip}", tags=["Actions"])
async def isolate_host(src_ip: str, current_user: str = Depends(verify_token)):
    """Enviar comando de aislamiento al agente (vía Integrations SOAR)."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{INTEGRATIONS_URL}/soar", json={
                "alert_id": f"MANUAL-{datetime.now().strftime('%H%M%S')}",
                "severity": "CRITICAL",
                "priority": "P1",
                "src_ip": src_ip
            }, timeout=5)
        logger.warning(f"[DASHBOARD] Aislamiento manual enviado para IP: {src_ip}")
        await manager.broadcast({"type": "action", "action": "isolate", "ip": src_ip, "status": "sent"})
        return {"status": "ok", "message": f"Comando de aislamiento enviado para {src_ip}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/kernel-status", tags=["Agents"])
async def get_kernel_status(current_user: str = Depends(verify_token)):
    """
    Fase 4: Estado del Kernel-Mode Driver por agente.
    Busca eventos de tipo kernel_driver_online en la DB y retorna el estado de cada agente.
    """
    try:
        col = db["triage_incidents"]
        pipeline = [
            {"$match": {"log_data.event_type": "kernel_driver_online"}},
            {
                "$group": {
                    "_id": "$log_data.src_ip",
                    "hostname": {"$last": "$log_data.source"},
                    "last_seen": {"$max": "$triage_ts"},
                    "driver_stats": {"$last": "$log_data.metadata.driver_stats"}
                }
            },
            {"$sort": {"last_seen": -1}}
        ]
        cursor = col.aggregate(pipeline)
        docs = await cursor.to_list(length=50)
        
        agents = []
        for doc in docs:
            agents.append({
                "ip":          doc["_id"],
                "hostname":    doc.get("hostname", "unknown"),
                "last_seen":   doc.get("last_seen"),
                "ring0_active": True,
                "driver_stats": doc.get("driver_stats", {})
            })
        
        return {"kernel_agents": agents, "count": len(agents)}
    except Exception as e:
        logger.error(f"[DASHBOARD] Error en kernel-status: {e}")
        return {"kernel_agents": [], "count": 0}

@app.post("/api/action/ticket/{alert_id}", tags=["Actions"])
async def create_ticket(alert_id: str, src_ip: str = "0.0.0.0", severity: str = "HIGH", current_user: str = Depends(verify_token)):
    """Crear ticket en sistema de ticketing."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{INTEGRATIONS_URL}/ticket", json={
                "alert_id": alert_id,
                "severity": severity,
                "priority": "P1" if severity == "CRITICAL" else "P2",
                "src_ip": src_ip
            }, timeout=5)
            result = resp.json()
        return {"status": "ok", "ticket_id": result.get("ticket_id")}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/topology", tags=["Dashboard"])
async def get_topology(current_user: str = Depends(verify_token)):
    """Retorna la topología de la red SATRI (Fase 7)"""
    return {
        "nodes": [
            {"id": "node-frontline", "label": "Nodo A (Frontline)", "group": "nodes"},
            {"id": "node-brain", "label": "Nodo B (Brain)", "group": "nodes"},
            {"id": "pod-mml", "label": "MML (Ingest)", "group": "frontline"},
            {"id": "pod-mcor", "label": "MCOR (Correlator)", "group": "frontline"},
            {"id": "pod-miaml", "label": "MIA_ML (UEBA)", "group": "frontline"},
            {"id": "pod-miavt", "label": "MIA_VT (Threat Intel)", "group": "brain"},
            {"id": "pod-mta", "label": "MTA (Triage)", "group": "brain"},
            {"id": "pod-integrations", "label": "Integrations (SOAR)", "group": "brain"}
        ],
        "links": [
            {"source": "pod-mml", "target": "pod-mcor"},
            {"source": "pod-mml", "target": "pod-miaml"},
            {"source": "pod-mcor", "target": "pod-mta"},
            {"source": "pod-miaml", "target": "pod-mta"},
            {"source": "pod-miavt", "target": "pod-mta"},
            {"source": "pod-mta", "target": "pod-integrations"}
        ]
    }

# ──────────────────────────────────────────────
# WebSocket endpoint
# ──────────────────────────────────────────────
@app.websocket("/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    logger.info(f"Nueva conexión WebSocket: {websocket.client}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ──────────────────────────────────────────────
# Servir el frontend
# ──────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("/app/static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/download/agent", tags=["Downloads"])
async def download_agent():
    """Descarga directa del agente SATRI para Windows."""
    agent_path = "/app/downloads/SATRI_Protection.exe"
    if os.path.exists(agent_path):
        return FileResponse(
            agent_path,
            media_type="application/octet-stream",
            filename="SATRI_Protection.exe"
        )
    return {"error": "Archivo no disponible. Contacte al administrador."}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "satri-dashboard", "connections": len(manager.active_connections)}

# Routers
from api.devices import router as devices_router
from api.topology import router as topology_router

app.include_router(devices_router)
app.include_router(topology_router)


