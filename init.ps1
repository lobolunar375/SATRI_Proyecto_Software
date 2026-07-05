# Inicialización de Tópicos de Kafka para SATRI Completo
$topics = @(
    "satri.logs.raw",
    "satri.logs.normalized",
    "satri.logs.enriched",
    "satri.alerts.enrichment",
    "satri.ioc.intelligence",
    "satri.correlated.alerts",
    "satri.incidents.triage"
)

foreach ($topic in $topics) {
    Write-Host "Creando tópico: $topic"
    docker exec satri-kafka kafka-topics --create --topic $topic --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --if-not-exists
}

Write-Host "Topics inicializados correctamente."
