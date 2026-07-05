# SATRI - Sistema de Análisis y Triage de Incidentes 🛡️

![SATRI Banner](https://img.shields.io/badge/Status-Production_Ready-success)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95-green)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)

SATRI es una plataforma integral de ciberseguridad diseñada bajo una arquitectura de microservicios distribuidos. Su ecosistema abarca desde la recolección de telemetría a nivel Kernel (Ring-0), pasando por extensiones de navegador y agentes de escritorio, hasta un backend escalable capaz de ingerir logs, correlacionar amenazas usando reglas MITRE ATT&CK, y ejecutar triage automatizado.

---

## 🚀 Arquitectura y Componentes Principales

El sistema implementa el flujo completo de un Security Operations Center (SOC) moderno, dividido en dos grandes frentes:

### 1. Nivel Endpoint (Telemetría y Aislamiento)
*   **Kernel Driver (Ring-0):** Un controlador de Windows en C puro que intercepta llamadas del sistema operativo para bloquear procesos maliciosos (ej. ransomware) antes de su ejecución.
*   **Agente Desktop:** Aplicación multiplataforma que monitorea tráfico de red y procesos locales, permitiendo el aislamiento remoto de la máquina a nivel de firewall de capa 3.
*   **Extensión de Navegador:** Protección antiphishing en tiempo real que previene conexiones a URLs maliciosas conocidas antes de que el navegador resuelva el DNS.

### 2. Nivel Backend (Análisis y Respuesta)
*   **Ingesta (MML):** Recepción de logs crudos, normalización a formato estándar y enriquecimiento de IPs (GeoIP).
*   **Inteligencia (MIA-VT):** Análisis de Indicadores de Compromiso (IoCs) respaldado por la API de VirusTotal.
*   **Correlación (MCOR):** Motor SIEM que detecta amenazas por comportamiento basado en 14 técnicas del framework **MITRE ATT&CK**.
*   **Triage (MTA):** Algoritmo automatizado que calcula el nivel de riesgo de cada incidente para su contención.

---

## 🛠️ Stack Tecnológico

*   **Core Backend:** Python 3.11, FastAPI (APIs REST y WebSockets para tiempo real).
*   **Frontend (Dashboard):** Single Page Application, Vanilla JS, Leaflet.js (Heatmap).
*   **Mensajería & Cola de Eventos:** Apache Kafka.
*   **Persistencia y Bases de Datos:**
    *   **OpenSearch:** Almacenamiento y búsqueda de logs masivos.
    *   **MongoDB:** Almacenamiento de alertas, tickets e IoCs.
    *   **Redis:** Caché de alta velocidad e implementaciones de Bloom Filters.
*   **Integración Continua (CI):** Pipeline en Jenkins utilizando Testcontainers (DooD) para pruebas de integración automatizadas.
*   **Infraestructura:** Docker, Docker Compose, Traefik (API Gateway).

---

## ⚙️ Instalación y Despliegue Local

### Requisitos Previos
*   Docker Desktop y Docker Compose.
*   Una API Key de VirusTotal.

### Pasos de Despliegue
1. Clonar el repositorio y acceder a la carpeta raíz.
2. Copiar el archivo `.env.example` a `.env` y configurar `VIRUSTOTAL_API_KEY`.
3. Desplegar los 14 microservicios orquestados:
   ```bash
   docker compose up -d --build
   ```
4. Inicializar los tópicos de Kafka (solo la primera vez):
   ```powershell
   # En Windows PowerShell
   .\init.ps1
   ```

---

## 📊 Dashboard SOC (Centro de Comando)

El sistema incluye una interfaz de monitoreo en tiempo real (SPA) accesible en:
*   **URL:** `http://localhost:3000`
*   **Usuario:** `admin` | **Password:** `satri2025`

**Características Clave:**
*   **Feed en Tiempo Real:** Las alertas ingresan instantáneamente al panel vía WebSockets sin recargar la página.
*   **Heatmap Global:** Mapa mundial interactivo que plotea el origen de los ataques detectados usando geolocalización de IPs.
*   **Botón de Aislamiento:** Capacidad de enviar una señal de contención remota para desconectar un endpoint comprometido de la red corporativa.

---

## 🛡️ Estándares y Cumplimiento

*   **Privacy by Design:** SATRI implementa anonimización de datos y minimización de recolección, cumpliendo estrictamente con las leyes de protección de datos personales (Ley N° 29733).
*   **Calidad de Código:** Flujo CI/CD automatizado vía **Jenkins** validando contratos de API mediante `pytest` y entornos efímeros con **Testcontainers**.

---
*SATRI v2.0 - Proyecto de Ingeniería de Software.*
