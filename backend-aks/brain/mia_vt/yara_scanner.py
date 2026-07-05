from pydantic import BaseModel
from typing import Literal
from extractor.ioc_extractor import IoC

class VTResult(BaseModel):
    vt_score: int # 0-100
    vt_label: Literal["CLEAN", "SUSPICIOUS", "MALICIOUS", "UNKNOWN"]
    malicious_count: int
    total_engines: int
    detection_ratio: float

def analyze_offline_intelligence(ioc: IoC) -> VTResult | None:
    """Simula reglas YARA o Threat Intelligence Local para artefactos que VT no analiza bien (ej. Bitcoin)"""
    if ioc.type == "btc_address":
        # Todo requerimiento de pago en Bitcoin extraido de un log/artefacto es sospechoso de Ransomware
        return VTResult(
            vt_score=95,
            vt_label="MALICIOUS",
            malicious_count=10,
            total_engines=10,
            detection_ratio=1.0
        )
    return None

def calculate_vt_score(vt_response: dict) -> VTResult:
    if "error" in vt_response or vt_response.get("status") == "NOT_FOUND":
        return VTResult(
            vt_score=0,
            vt_label="UNKNOWN",
            malicious_count=0,
            total_engines=0,
            detection_ratio=0.0
        )

    stats = vt_response.get("last_analysis_stats", {})
    malicious = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)
    total = sum(stats.values()) or 1
    
    # Formula ponderada: malicious pesa 1.0, suspicious 0.5
    weighted = (malicious * 1.0 + suspicious * 0.5) / total
    score = int(min(100, weighted * 100))
    
    # Bonus por reputacion negativa de VT
    reputation = vt_response.get("reputation", 0)
    if reputation < -10:
        score = min(100, score + 10)
        
    if score >= 60:
        label = "MALICIOUS"
    elif score >= 25:
        label = "SUSPICIOUS"
    else:
        label = "CLEAN"
        
    return VTResult(
        vt_score=score,
        vt_label=label,
        malicious_count=malicious,
        total_engines=total,
        detection_ratio=round(malicious / total, 3)
    )

