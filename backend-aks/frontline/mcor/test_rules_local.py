"""
Script de prueba para disparar las 14 reglas de MCOR localmente
y verificar que la lógica de correlación funciona correctamente.
"""
from rules import run_all_rules
from time_window_engine import clear_chain, r
import json

def test_rule(name: str, events: list[dict]):
    print(f"\n--- Probando {name} ---")
    
    # Limpiar estado previo
    for event in events:
        if "src_ip" in event:
            r.delete(f"mcor:r01:bf:{event['src_ip']}")
            r.delete(f"mcor:r02:esc:{event['src_ip']}")
            r.delete(f"mcor:bf_flagged:{event['src_ip']}")
            r.delete(f"mcor:esc_flagged:{event['src_ip']}")
            r.delete(f"mcor:r09:ransom:{event['src_ip']}")
            r.delete(f"mcor:r10:exfil:{event['src_ip']}")
            r.delete(f"mcor:bl_flagged:{event['src_ip']}")
    
    triggered_alerts = []
    for event in events:
        alerts = run_all_rules(event)
        if alerts:
            triggered_alerts.extend(alerts)
            
    if triggered_alerts:
        print("✅ ALERTA GENERADA:")
        for alert in triggered_alerts:
            print(json.dumps(alert, indent=2, ensure_ascii=False))
    else:
        print("❌ NO SE GENERÓ ALERTA")


if __name__ == "__main__":
    ip_test = "10.0.0.50"
    
    # Regla 01: Fuerza Bruta
    test_rule("Regla 01: Fuerza Bruta SSH (5 fallos)", [
        {"event_type": "ssh_fail", "src_ip": ip_test} for _ in range(5)
    ])
    
    # Regla 02: Escalada de Privilegios
    test_rule("Regla 02: Sudo Fail (3 fallos)", [
        {"event_type": "sudo_fail", "src_ip": ip_test} for _ in range(3)
    ])
    
    # Regla 03: Ataque Multi-Etapa
    # Nota: ya disparamos R1 y R2 para esta IP, sus flags deberían estar activos,
    # pero como limpiamos el estado en cada test_rule, vamos a simularlo en uno solo.
    test_rule("Regla 03: Multi-Etapa", 
        [{"event_type": "ssh_fail", "src_ip": "10.0.0.60"} for _ in range(5)] +
        [{"event_type": "sudo_fail", "src_ip": "10.0.0.60"} for _ in range(3)]
    )

    # Regla 04: Proceso Desconocido
    test_rule("Regla 04: Proceso Desconocido", [
        {"event_type": "process_execution", "process_name": "mimikatz.exe", "src_ip": ip_test}
    ])

    # Regla 05: Descarga ejecutable
    test_rule("Regla 05: Descarga ejecutable", [
        {"event_type": "file_download", "file_name": "payload.ps1", "src_ip": ip_test}
    ])

    # Regla 07: Creación cuenta
    test_rule("Regla 07: Creación de cuenta", [
        {"event_type": "user_add", "src_ip": ip_test}
    ])

    # Regla 08: Tarea programada
    test_rule("Regla 08: Tarea programada", [
        {"event_type": "process_execution", "message": "schtasks /create /tn maliciosa", "src_ip": ip_test}
    ])

    # Regla 09: Ransomware FIM
    test_rule("Regla 09: Ransomware FIM (10 renombrados)", [
        {"event_type": "file_rename", "file_name": f"doc{i}.locked", "src_ip": ip_test} for i in range(10)
    ])

    # Regla 10: Exfiltración
    test_rule("Regla 10: Exfiltración > 500MB", [
        {"event_type": "network_traffic", "bytes_sent": 600 * 1024 * 1024, "src_ip": ip_test}
    ])

    # Regla 12: Desactivación seguridad
    test_rule("Regla 12: Desactivación seguridad", [
        {"event_type": "service_stop", "service_name": "Windows Defender", "src_ip": ip_test}
    ])

    # Regla 13: DNS Tunneling
    test_rule("Regla 13: DNS Tunneling (>50 requests, long subdomains)", [
        {"event_type": "dns_query", "domain": "a"*35 + ".evil.com", "src_ip": ip_test} for _ in range(50)
    ])

    # Regla 14: UEBA Anomaly
    test_rule("Regla 14: UEBA Anomaly", [
        {"event_type": "ueba_anomaly", "anomaly_score": 0.85, "src_ip": ip_test}
    ])

