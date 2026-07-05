import importlib
import pkgutil
import os
import sys

from loguru import logger

# Cargar automáticamente todos los módulos de reglas en este directorio
rule_modules = []

current_dir = os.path.dirname(__file__)
for _, module_name, _ in pkgutil.iter_modules([current_dir]):
    if module_name.startswith("regla_"):
        try:
            module = importlib.import_module(f"rules.{module_name}")
            if hasattr(module, "evaluate"):
                rule_modules.append(module)
                logger.info(f"Regla cargada: {module.RULE_NAME} ({module.MITRE_ID})")
        except Exception as e:
            logger.error(f"Error cargando regla {module_name}: {e}")

def run_all_rules(event: dict) -> list[dict]:
    """Ejecuta todas las reglas sobre un evento y retorna las alertas generadas."""
    alerts = []
    for module in rule_modules:
        try:
            result = module.evaluate(event)
            if result:
                alerts.append(result)
        except Exception as e:
            logger.error(f"Error ejecutando regla {module.RULE_NAME}: {e}")
    return alerts
