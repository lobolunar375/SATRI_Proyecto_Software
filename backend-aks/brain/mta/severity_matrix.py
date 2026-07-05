# Matriz de Decision: Define que accion tomar segun Gravedad e Inteligencia
DECISION_MATRIX = {
    ("CRITICAL", "MALICIOUS"): ("BLOCK",       "P1", True),
    ("CRITICAL", "SUSPICIOUS"):("ESCALATE",    "P1", False),
    ("CRITICAL", "CLEAN"):     ("INVESTIGATE", "P2", False),
    ("HIGH", "MALICIOUS"):     ("BLOCK",       "P1", False),
    ("HIGH", "SUSPICIOUS"):    ("ESCALATE",    "P2", False),
    ("MEDIUM", "MALICIOUS"):   ("ESCALATE",    "P2", False),
    ("MEDIUM", "SUSPICIOUS"):  ("INVESTIGATE", "P3", False),
    ("LOW", "MALICIOUS"):      ("INVESTIGATE", "P3", False),
    ("LOW", "SUSPICIOUS"):     ("MONITOR",     "P4", False),
}

def get_triage_action(severity, vt_label, ueba_score=0.0):
    # Si MIA_ML detecta alta anomalía (score negativo grande en Isolation Forest),
    # elevamos la severidad base de MCOR.
    final_severity = severity
    if ueba_score < -0.5 and severity in ["LOW", "MEDIUM"]:
        final_severity = "HIGH"
    elif ueba_score < -0.8 and severity == "HIGH":
        final_severity = "CRITICAL"
        
    action, priority, ir = DECISION_MATRIX.get((final_severity, vt_label), ("ESCALATE", "P2", False))
    return action, priority, ir, final_severity
