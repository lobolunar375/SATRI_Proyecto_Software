import asyncio
import websockets
import json
import logging
from reporter import reporter

logger = logging.getLogger("browser_bridge")

async def handle_client(websocket):
    logger.info("Browser extension conectada al bridge.")
    try:
        async for message in websocket:
            data = json.loads(message)
            event_type = data.get("event_type", "browser_event")
            severity = data.get("severity", "MEDIUM")
            details = data.get("details", {})
            
            logger.info(f"Evento recibido de extension: {event_type} - {severity}")
            msg = f"Actividad en Navegador: {event_type}"
            if "url" in details:
                msg += f" | URL: {details['url']}"
            if "filename" in details:
                msg += f" | Archivo: {details['filename']}"
                
            # Enviar al backend (SOAR/SIEM) via el reporter
            reporter.send_event(
                event_type=event_type, 
                message=msg, 
                severity=severity, 
                artifacts=details
            )
    except websockets.exceptions.ConnectionClosed:
        logger.info("Browser extension desconectada.")
    except Exception as e:
        logger.error(f"Error procesando mensaje del browser: {e}")

async def start_bridge_async():
    logger.info("Iniciando Browser Bridge en ws://127.0.0.1:19847")
    try:
        async with websockets.serve(handle_client, "127.0.0.1", 19847):
            await asyncio.Future()  # run forever
    except Exception as e:
        logger.error(f"Fallo al iniciar el servidor WebSocket: {e}")

def start_browser_bridge():
    # Creamos un nuevo event loop para este hilo
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_bridge_async())
