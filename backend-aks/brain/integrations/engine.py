import os
import yaml
import httpx
import asyncio
import uuid
from loguru import logger
from datetime import datetime, timezone

PLAYBOOKS_DIR = "/app/playbooks"
MML_API_URL = os.getenv("MML_API_URL", "http://mml:8000/api/v1")

# ── Cola de aprobaciones Human-in-the-Loop ──
# Acciones destructivas requieren aprobación antes de ejecutarse
pending_approvals = {}  # {approval_id: {action, alert_data, playbook_name, created_at, status}}


class SOAREngine:
    def __init__(self):
        self.playbooks = self.load_playbooks()
        self.execution_log = []  # Historial de ejecuciones
        
    def load_playbooks(self):
        loaded = []
        if not os.path.exists(PLAYBOOKS_DIR):
            logger.warning(f"Directorio de playbooks no encontrado: {PLAYBOOKS_DIR}")
            return loaded
            
        for file in os.listdir(PLAYBOOKS_DIR):
            if file.endswith(".yml") or file.endswith(".yaml"):
                path = os.path.join(PLAYBOOKS_DIR, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        pb = yaml.safe_load(f)
                        loaded.append(pb)
                        logger.info(f"Playbook cargado: {pb.get('name')}")
                except Exception as e:
                    logger.error(f"Error cargando playbook {file}: {e}")
        return loaded
        
    def match_playbooks(self, alert_data):
        """Busca qué playbooks coinciden con los atributos de la alerta"""
        matched = []
        severity = alert_data.get("severity", "").upper()
        # Buscar rule_name en múltiples campos posibles
        rule = (
            alert_data.get("rule_name") or 
            alert_data.get("correlation_rule") or 
            ""
        ).lower()
        
        for pb in self.playbooks:
            trigger_sev = pb.get("trigger_severity", "").upper()
            trigger_rule = pb.get("trigger_rule", "").lower()
            
            match_sev = (trigger_sev == severity) if trigger_sev else False
            match_rule = (trigger_rule in rule) if trigger_rule else False
            
            if trigger_sev and trigger_rule:
                if match_sev and match_rule:
                    matched.append(pb)
            elif trigger_sev and match_sev:
                matched.append(pb)
            elif trigger_rule and match_rule:
                matched.append(pb)
                
        return matched

    async def execute(self, alert_data):
        """Ejecuta los playbooks que hagan match con la alerta"""
        playbooks = self.match_playbooks(alert_data)
        
        if not playbooks:
            logger.info(f"[SOAR] Sin playbooks para: {alert_data.get('alert_id', 'N/A')}")
            return {"status": "no_playbook"}
            
        results = []
        for pb in playbooks:
            pb_name = pb.get("name", "Unknown")
            logger.critical(f"[SOAR] 🚀 INICIANDO PLAYBOOK: {pb_name}")
            pb_result = {"playbook": pb_name, "actions": [], "timestamp": datetime.now(timezone.utc).isoformat()}
            
            for action in pb.get("actions", []):
                act_type = action.get("type")
                requires_approval = action.get("requires_approval", False)
                
                # ── HUMAN-IN-THE-LOOP ──
                # Acciones de tipo "isolate_host" requieren aprobación por defecto
                if act_type == "isolate_host" or requires_approval:
                    approval_id = self._request_approval(action, alert_data, pb_name)
                    logger.warning(f"[SOAR] ⏳ APROBACION REQUERIDA: {act_type} → ID: {approval_id}")
                    pb_result["actions"].append({
                        "type": act_type, 
                        "result": "pending_approval",
                        "approval_id": approval_id
                    })
                    continue
                
                logger.info(f"[SOAR] -> Ejecutando accion: {act_type}")
                
                if act_type == "slack_notify":
                    res = await self._action_slack(action, alert_data)
                    pb_result["actions"].append({"type": act_type, "result": res})
                    
                elif act_type == "create_ticket":
                    res = await self._action_ticket(action, alert_data)
                    pb_result["actions"].append({"type": act_type, "result": res})
                    
                else:
                    logger.warning(f"[SOAR] Accion desconocida: {act_type}")
                    pb_result["actions"].append({"type": act_type, "result": "unknown_action"})
                    
            results.append(pb_result)
            self.execution_log.append(pb_result)
            # Mantener solo últimas 100 ejecuciones en memoria
            if len(self.execution_log) > 100:
                self.execution_log = self.execution_log[-100:]
            
        return {"status": "executed", "playbooks": results}

    # ── HUMAN-IN-THE-LOOP: Solicitar aprobación ──
    def _request_approval(self, action, alert_data, playbook_name):
        approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
        pending_approvals[approval_id] = {
            "action": action,
            "alert_data": alert_data,
            "playbook_name": playbook_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "PENDING",
            "src_ip": alert_data.get("src_ip", "N/A"),
            "severity": alert_data.get("severity", "UNKNOWN"),
            "action_type": action.get("type", "unknown"),
        }
        return approval_id

    # ── HUMAN-IN-THE-LOOP: Aprobar o rechazar ──
    async def approve(self, approval_id):
        if approval_id not in pending_approvals:
            return {"status": "error", "message": "Approval ID not found"}
        
        entry = pending_approvals[approval_id]
        if entry["status"] != "PENDING":
            return {"status": "error", "message": f"Already {entry['status']}"}
        
        action = entry["action"]
        alert_data = entry["alert_data"]
        act_type = action.get("type")
        
        logger.critical(f"[SOAR] ✅ APROBADO por analista: {approval_id} → {act_type}")
        
        # Ejecutar la acción ahora que fue aprobada
        if act_type == "isolate_host":
            result = await self._action_isolate(action, alert_data)
        else:
            result = "executed"
        
        entry["status"] = "APPROVED"
        entry["executed_at"] = datetime.now(timezone.utc).isoformat()
        entry["result"] = result
        return {"status": "ok", "result": result, "approval_id": approval_id}

    async def reject(self, approval_id):
        if approval_id not in pending_approvals:
            return {"status": "error", "message": "Approval ID not found"}
        
        entry = pending_approvals[approval_id]
        entry["status"] = "REJECTED"
        entry["rejected_at"] = datetime.now(timezone.utc).isoformat()
        logger.warning(f"[SOAR] ❌ RECHAZADO por analista: {approval_id}")
        return {"status": "ok", "approval_id": approval_id}
        
    # ── EJECUTORES DE ACCIÓN ──
    async def _action_isolate(self, action, alert_data):
        ip = alert_data.get("src_ip")
        if not ip or ip == "0.0.0.0" or ip == "N/A":
            return "failed_no_ip"
            
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(f"{MML_API_URL}/agent/config/{ip}/isolate", timeout=5)
                if r.status_code == 200:
                    logger.success(f"[SOAR] ✔️ Aislamiento remoto activado para IP: {ip}")
                    return "success"
                else:
                    logger.error(f"[SOAR] Fallo aislamiento en MML: {r.status_code}")
                    return "failed_api"
        except Exception as e:
            logger.error(f"[SOAR] Error en accion isolate: {e}")
            return "error"
            
    async def _action_slack(self, action, alert_data):
        msg = action.get("message", "").replace("$src_ip", alert_data.get("src_ip", "N/A"))
        channel = action.get("channel", "#general")
        
        logger.warning(f"💬 [SLACK {channel}] {msg}")
        return "success"
        
    async def _action_ticket(self, action, alert_data):
        prio = action.get("priority", "P3")
        alert_id = str(alert_data.get('alert_id', 'UNKNOWN'))
        ticket_id = f"SOAR-{datetime.now().strftime('%Y%m%d')}-{alert_id[-4:]}"
        
        logger.warning(f"🎫 [JIRA] Ticket automático: {ticket_id} | Prioridad: {prio}")
        return ticket_id
