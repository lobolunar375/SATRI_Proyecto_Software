import time
import logging
import psutil
from reporter import reporter

logger = logging.getLogger("network_monitor")

def start_network_monitor():
    logger.info("Iniciando Monitor de Red en tiempo real (psutil)...")
    seen_connections = set()
    
    while True:
        try:
            current_connections = psutil.net_connections(kind='inet')
            for conn in current_connections:
                if conn.raddr:
                    src_ip = conn.laddr.ip if conn.laddr else "unknown"
                    src_port = conn.laddr.port if conn.laddr else 0
                    dst_ip = conn.raddr.ip
                    dst_port = conn.raddr.port
                    
                    # IGNORAR conexiones del propio agente hacia el SIEM
                    if dst_port in [8000, 18001, 19847, 7071]:
                        continue
                        
                    # IGNORAR conexiones de localhost a localhost (ruido de sistema)
                    if dst_ip in ["127.0.0.1", "::1"] or dst_ip.startswith("127."):
                        continue
                        
                    # IGNORAR peticiones DNS locales (demasiado ruido)
                    if dst_port == 53:
                        continue
                        
                    # Filtrar TCP que no estén ESTABLECIDAS (opcional, pero reduce ruido)
                    if conn.type == 1 and conn.status != "ESTABLISHED": # SOCK_STREAM
                        continue
                        
                    conn_id = (src_ip, src_port, dst_ip, dst_port, conn.pid)
                    if conn_id not in seen_connections:
                        seen_connections.add(conn_id)
                        
                        proc_name = "Proceso del Sistema"
                        if conn.pid:
                            try:
                                proc = psutil.Process(conn.pid)
                                proc_name = proc.name()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                proc_name = f"ProcID:{conn.pid}"
                                
                        reporter.send_event(
                            event_type="network_flow",
                            message=f"[{proc_name}] se conectó a {dst_ip}:{dst_port}",
                            severity="INFO",
                            artifacts={
                                "src_ip": src_ip,
                                "src_port": src_port,
                                "dst_ip": dst_ip,
                                "dst_port": dst_port,
                                "process_name": proc_name,
                                "pid": conn.pid,
                                "status": conn.status
                            }
                        )
            
            if len(seen_connections) > 10000:
                seen_connections.clear()
                
        except Exception as e:
            logger.error(f"Error en network monitor: {e}")
            
        time.sleep(2)
