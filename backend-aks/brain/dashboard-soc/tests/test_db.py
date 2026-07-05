import pytest
from testcontainers.mongodb import MongoDbContainer
from motor.motor_asyncio import AsyncIOMotorClient

# Habilitar soporte para funciones async en pytest
pytest_plugins = ('pytest_asyncio',)

@pytest.fixture(scope="module")
def mongodb_container():
    """
    Inicia un contenedor de MongoDB (efímero) al empezar los tests del módulo
    y lo destruye automáticamente al terminar.
    """
    with MongoDbContainer("mongo:6.0") as mongo:
        yield mongo

@pytest.mark.asyncio
async def test_triage_incidents_insertion(mongodb_container):
    """
    Prueba automatizada que verifica la capacidad de conectar e interactuar
    con la base de datos de manera aislada utilizando Testcontainers.
    """
    # 1. Obtener la URI dinámica asignada por Docker
    connection_url = mongodb_container.get_connection_url().replace("localnpipe", "localhost")
    
    # 2. Conectar el cliente asyncrónico de Motor a la base de datos de prueba
    client = AsyncIOMotorClient(connection_url)
    db = client["satri_test_db"]
    collection = db["triage_incidents"]
    
    # 3. Datos mock simulando un incidente generado por el sistema
    mock_incident = {
        "src_ip": "192.168.1.100",
        "event_type": "malicious_process_killed",
        "severity": "CRITICAL",
        "triage_decision": "BLOCK",
        "message": "Se detectó y aniquiló ransomware.exe"
    }
    
    # 4. Insertar en MongoDB
    insert_result = await collection.insert_one(mock_incident)
    assert insert_result.inserted_id is not None
    
    # 5. Recuperar el documento y verificar sus datos
    retrieved_doc = await collection.find_one({"_id": insert_result.inserted_id})
    assert retrieved_doc is not None
    assert retrieved_doc["severity"] == "CRITICAL"
    assert retrieved_doc["triage_decision"] == "BLOCK"
    
    # 6. Limpiar (Opcional, ya que Testcontainers destruirá el contenedor completo)
    client.close()
