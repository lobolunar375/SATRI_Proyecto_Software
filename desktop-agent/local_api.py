from fastapi import FastAPI
from modules.firewall_local import isolate_network

app = FastAPI(title="SATRI Local Agent API")

@app.post("/isolate")
def isolate_endpoint():
    """Endpoint expuesto para que SOAR aísle el equipo"""
    isolate_network()
    return {"status": "success", "message": "Host aislado."}

def run_local_api():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18001, log_config=None)
