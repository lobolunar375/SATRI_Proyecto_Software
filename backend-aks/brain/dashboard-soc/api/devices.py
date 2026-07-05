from fastapi import APIRouter, Depends, HTTPException, Request
import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/api/v1/devices", tags=["Devices"])
logger = logging.getLogger("devices")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://satri:satri2025@mongodb:27017")
client = None

def get_telemetry_db():
    global client
    if client is None:
        client = AsyncIOMotorClient(MONGO_URI)
    return client["satri_telemetry_db"]

def check_admin_role():
    # En producción esto verificaría el token JWT
    return True

@router.get("/")
async def list_devices(is_admin: bool = Depends(check_admin_role)):
    if not is_admin:
        raise HTTPException(status_code=403, detail="Acceso denegado. Se requiere rol de Admin.")
    
    db = get_telemetry_db()
    devices_cursor = db.devices.find({}, {"_id": 0})
    devices = await devices_cursor.to_list(length=100)
    
    # Adaptar para el dashboard si es necesario
    formatted_devices = []
    for d in devices:
        formatted_devices.append({
            "id": d.get("device_id", "Unknown"),
            "hostname": d.get("device_id", "Unknown"),
            "status": d.get("status", "ONLINE"),
            "ip": d.get("ip_address", "Unknown"),
            "agent_version": d.get("agent_version", "1.0.0"),
            "last_seen": d.get("last_seen", "Unknown")
        })
        
    return {"devices": formatted_devices}

from pydantic import BaseModel
from datetime import datetime, timezone

class HeartbeatReq(BaseModel):
    device_id: str
    os_version: str
    agent_version: str

@router.post("/heartbeat")
async def receive_heartbeat(req: HeartbeatReq, request: Request):
    db = get_telemetry_db()
    # Upsert the device using motor
    await db.devices.update_one(
        {"device_id": req.device_id},
        {"$set": {
            "os_version": req.os_version,
            "agent_version": req.agent_version,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "status": "ONLINE",
            "ip_address": request.client.host
        }},
        upsert=True
    )
    return {"status": "ok"}

@router.post("/{device_id}/isolate")
async def isolate_device(device_id: str, is_admin: bool = Depends(check_admin_role)):
    if not is_admin:
        raise HTTPException(status_code=403, detail="Acceso denegado. Se requiere rol de Admin.")
    
    # Obtener IP del dispositivo
    db = get_telemetry_db()
    device = await db.devices.find_one({"device_id": device_id})
    
    if device and device.get("ip_address"):
        target_ip = device.get("ip_address")
        # Enviar petición a Integrations (SOAR) para aislar la IP si es necesario
        # o directamente al agente (push) si tiene IP fija.
        # Por ahora, registramos la acción.
        logger.info(f"Comando de aislamiento emitido para {device_id} con IP {target_ip}")
        return {"status": "isolated", "device_id": device_id, "message": f"Comando de aislamiento enviado a {target_ip}."}
    else:
        return {"status": "error", "device_id": device_id, "message": "Dispositivo no encontrado o sin IP registrada."}
