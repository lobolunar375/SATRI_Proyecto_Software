import os
from loguru import logger
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime

REPORTS_DIR = os.getenv("REPORTS_DIR", "/app/reports")

def ensure_dir():
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)

def generate_pdf_report(alert: dict) -> str:
    ensure_dir()
    
    alert_id = alert.get("alert_id", "UNKNOWN")
    filename = f"report_{alert_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)
    
    try:
        c = canvas.Canvas(filepath, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, f"SATRI - Reporte de Incidente Crítico")
        
        c.setFont("Helvetica", 12)
        c.drawString(50, 710, f"ID de Alerta: {alert_id}")
        c.drawString(50, 690, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.drawString(50, 670, f"Regla Correlacionada: {alert.get('rule_name', 'N/A')}")
        c.drawString(50, 650, f"Severidad: {alert.get('severity', 'N/A')}")
        c.drawString(50, 630, f"Prioridad: {alert.get('priority', 'N/A')}")
        c.drawString(50, 610, f"IP de Origen: {alert.get('src_ip', 'N/A')}")
        c.drawString(50, 590, f"Decisión de Triage: {alert.get('triage_decision', 'N/A')}")
        
        c.drawString(50, 550, "Detalles Técnicos:")
        
        reason = alert.get('correlation_reason', 'N/A')
        # Simple word wrap
        y = 530
        for line in [reason[i:i+80] for i in range(0, len(reason), 80)]:
            c.drawString(70, y, line)
            y -= 20
        
        c.save()
        logger.success(f"[REPORTS] Reporte PDF generado: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"[REPORTS] Error generando PDF: {e}")
        return ""
