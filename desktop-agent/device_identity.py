import uuid
import os
import json

IDENTITY_FILE = "device_id.json"

def get_device_identity():
    if os.path.exists(IDENTITY_FILE):
        with open(IDENTITY_FILE, "r") as f:
            data = json.load(f)
            return data["device_id"]
    
    # Generar nuevo si no existe
    new_id = f"DEV-{uuid.uuid4().hex[:8].upper()}"
    with open(IDENTITY_FILE, "w") as f:
        json.dump({"device_id": new_id}, f)
    return new_id
