# 🛡️ SATRI — Modelo de Privacidad y Consentimiento
**Documento de Fase 0 (BLOQUEANTE)**  
Ningún código de recolección de datos se escribe hasta que este documento sea aprobado.

**Marco Legal de Referencia:** Ley de Protección de Datos Personales N° 29733 (Perú)

---

## 1. Principio Fundamental

> **Criterio de decisión:** Solo se envía lo necesario para que el panel central entienda  
> _"hubo una amenaza de tipo X con severidad Y"_ o _"el comportamiento de sesión es estadísticamente inusual"_,  
> nunca _"qué estaba haciendo exactamente la persona o qué contenido visitó"_.

---

## 2. Esquema del Evento Agregado (JSON)

Este es el **único** formato de datos que la app de escritorio puede enviar al backend.  
Cualquier campo fuera de este esquema es **rechazado** por la Azure Function receptora.

```json
{
  "schema_version": "1.1",
  "event_id": "evt-a1b2c3d4",
  "device_id": "dev-hashed-uuid",
  "timestamp": "2026-06-18T06:00:00Z",
  "event_type": "suspicious_process_detected",
  "severity": "HIGH",
  "category": "process_monitor",
  "details": {
    "resource_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "action_taken": "blocked",
    "threat_name": "Trojan.GenericKD",
    "vt_score": "12/72",
    "geo_country": "RU",
    "geo_city": "Moscow",
    "geo_asn": "AS12345"
  },
  "behavior_metrics": {
    "login_hour": 6,
    "day_of_week": 4,
    "session_duration_minutes": 120,
    "actions_per_minute_avg": 2.5
  },
  "app_version": "2.0.0"
}
```

### 2.1 Campos Permitidos (exhaustivo)

| Campo | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `event_id` | string | ID único del evento | `"evt-a1b2c3d4"` |
| `device_id` | string | UUID hasheado del dispositivo | `"dev-hashed-uuid"` |
| `timestamp` | ISO 8601 | Momento de la detección | `"2026-06-18T06:00:00Z"` |
| `event_type` | enum | Tipo de evento (ver §2.2) | `"suspicious_process_detected"` |
| `severity` | enum | LOW / MEDIUM / HIGH / CRITICAL | `"HIGH"` |
| `category` | enum | Módulo que generó el evento | `"process_monitor"` |
| `details.resource_hash` | string | Hash SHA-256 del recurso sospechoso | `"sha256:e3b0..."` |
| `details.action_taken` | enum | detected / blocked / quarantined / isolated | `"blocked"` |
| `details.threat_name` | string | Nombre genérico de la amenaza | `"Trojan.GenericKD"` |
| `details.vt_score` | string | Score de VirusTotal | `"12/72"` |
| `details.geo_country` | string | País según IP (ISO 3166-1 alpha-2) | `"RU"` |
| `details.geo_city` | string | Ciudad aproximada según IP | `"Moscow"` |
| `details.geo_asn` | string | ASN del proveedor de internet | `"AS12345"` |
| `behavior_metrics.login_hour` | integer | Hora del día (0-23) | `6` |
| `behavior_metrics.day_of_week` | integer | Día de la semana (1-7) | `4` |
| `behavior_metrics.session_duration_minutes` | integer | Duración en minutos | `120` |
| `behavior_metrics.actions_per_minute_avg` | float | Frecuencia de acciones | `2.5` |
| `app_version` | string | Versión del agente | `"2.0.0"` |

### 2.2 Valores Permitidos para `event_type` y `category`

| `event_type` | `category` |
|---|---|
| `suspicious_process_detected` | `process_monitor` |
| `ransomware_behavior_detected` | `ransomware_guard` |
| `malicious_download_detected` | `download_scanner` |
| `firewall_rule_triggered` | `firewall_local` |
| `insecure_wifi_detected` | `wifi_check` |
| `insecure_page_blocked` | `browser_extension` |
| `anomalous_behavior_detected` | `ueba_engine` |

---

## 3. Campos PROHIBIDOS (nunca enviar)

> ⛔ Si cualquier módulo intenta enviar alguno de estos campos, el sistema debe **rechazar** el evento antes de transmitirlo.

| Campo Prohibido | Razón |
|---|---|
| `url` / `visited_url` / `page_url` | Revela actividad de navegación |
| `page_content` / `page_title` | Revela contenido visitado |
| `window_title` / `active_window` | Revela aplicación/documento en uso |
| `browsing_history` | Historial completo de navegación |
| `screenshot` / `screen_capture` | Captura visual de actividad |
| `keystrokes` / `keylog` | Keylogging |
| `clipboard` / `clipboard_content` | Contenido del portapapeles |
| `file_content` / `document_content` | Contenido de archivos personales |
| `file_path` | Ruta completa (revela estructura personal) |
| `file_name` | Nombre de archivos personales |
| `password` / `credentials` | Credenciales del usuario |
| `gps_location` / `precise_location` | Ubicación GPS precisa |
| `email` / `personal_email` | Correo personal |
| `username` / `system_user` | Nombre de usuario del SO |
| `hostname` | Nombre del equipo |

---

## 4. Texto de Consentimiento (Pantalla de Onboarding)

### SATRI Endpoint Protection — Información de Privacidad

**¿Qué hace esta aplicación?**
SATRI protege tu computadora detectando amenazas de seguridad como procesos maliciosos, ransomware, descargas peligrosas y redes WiFi inseguras.

**¿Qué datos se envían?**
Cuando se detecta una amenaza, se envía **únicamente**:
- ✅ Tipo de amenaza detectada y nivel de severidad.
- ✅ Fecha y hora de la detección.
- ✅ Hash del archivo sospechoso (código único, no el archivo).
- ✅ Acción tomada (detectado, bloqueado, aislado).

**Análisis de Comportamiento (UEBA):**
Para detectar ataques sofisticados, SATRI analiza estadísticamente tus patrones de uso:
- ✅ Horario de inicio de sesión y duración.
- ✅ Frecuencia promedio de acciones.
- ✅ Geolocalización aproximada (país/ciudad, NUNCA GPS preciso).

**¿Qué datos NUNCA se envían?**
- ❌ Páginas web que visitas ni historiales de navegación.
- ❌ Archivos personales, contraseñas o contenido.
- ❌ Capturas de pantalla o lo que escribes en el teclado.
- ❌ Tu ubicación exacta.

**Tus derechos:**
- 📋 Puedes ver exactamente qué se ha reportado en cualquier momento.
- ⏸️ Puedes pausar el envío de reportes cuando quieras.
- 🗑️ Puedes desinstalar la aplicación limpiamente en cualquier momento.

**Al hacer clic en "Aceptar", confirmas que:**
1. Has leído y entendido qué datos de seguridad y comportamiento se recolectan.
2. Autorizas explícitamente el envío de alertas de seguridad y métricas de comportamiento al panel central.
3. Sabes que puedes pausar o desinstalar en cualquier momento.

`[Aceptar]`  `[Rechazar y Salir]`

---

**Documento creado:** 2026-06-19  
**Estado:** ✅ APROBADO  
**Siguiente paso:** Fase 1 (MML - Nodo A)
