import json
import os

CONFIG_FILE = "agent_config.json"

DEFAULT_CONFIG = {
    "auto_block": True,
    "isolation_mode": False,
    "log_level": "INFO",
    "backend_url": "http://172.212.5.28:8000"
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return DEFAULT_CONFIG

def should_auto_block():
    cfg = load_config()
    return cfg.get("auto_block", True)

def is_isolated():
    cfg = load_config()
    return cfg.get("isolation_mode", False)
