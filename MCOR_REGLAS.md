# MCOR — 14 Reglas de Correlación MITRE ATT&CK
### Documento de revisión previo a la implementación (Fase 2)

---

## Regla 01: Fuerza bruta SSH
- **Técnica MITRE:** T1110 (Brute Force)
- **Condición:** >= 5 intentos fallidos de autenticación desde la misma IP en 2 minutos
- **Ventana de tiempo:** 2 min
- **Severidad:** CRITICAL
- **Archivo:** `rules/regla_01_fuerza_bruta_ssh.py`

## Regla 02: Escalada de privilegios vía sudo fallido
- **Técnica MITRE:** T1548 (Abuse Elevation Control Mechanism)
- **Condición:** >= 3 intentos fallidos de sudo/su tras un login exitoso, en 5 minutos
- **Ventana de tiempo:** 5 min
- **Severidad:** HIGH
- **Archivo:** `rules/regla_02_escalada_sudo.py`

## Regla 03: Ataque multi-etapa (fuerza bruta + escalada)
- **Técnica MITRE:** T1110 + T1548 correlacionadas
- **Condición:** Regla 01 disparada, seguida de Regla 02 disparada, mismo origen, ventana de 10 min
- **Ventana de tiempo:** 10 min
- **Severidad:** CRITICAL
- **Archivo:** `rules/regla_03_multi_etapa_bruta_escalada.py`

## Regla 04: Ejecución de proceso desconocido
- **Técnica MITRE:** T1059 (Command and Scripting Interpreter)
- **Condición:** Proceso ejecutado que no está en la whitelist de procesos conocidos del sistema
- **Ventana de tiempo:** instantánea (evento individual)
- **Severidad:** MEDIUM
- **Archivo:** `rules/regla_04_proceso_desconocido.py`

## Regla 05: Descarga de archivo ejecutable inusual
- **Técnica MITRE:** T1105 (Ingress Tool Transfer)
- **Condición:** Descarga de archivo .exe/.bat/.ps1/.sh/.msi/.dll desde fuente no confiable
- **Ventana de tiempo:** instantánea
- **Severidad:** HIGH
- **Archivo:** `rules/regla_05_descarga_ejecutable.py`

## Regla 06: Conexión a IP en lista negra
- **Técnica MITRE:** T1071 (Application Layer Protocol)
- **Condición:** Conexión saliente a IP/dominio marcado como malicioso en la base de IoC
- **Ventana de tiempo:** instantánea
- **Severidad:** HIGH
- **Archivo:** `rules/regla_06_ip_lista_negra.py`

## Regla 07: Creación de cuenta de usuario nueva
- **Técnica MITRE:** T1136 (Create Account)
- **Condición:** Evento de creación de cuenta local (`net user /add` en Windows, `useradd` en Linux)
- **Ventana de tiempo:** instantánea
- **Severidad:** MEDIUM
- **Archivo:** `rules/regla_07_creacion_cuenta.py`

## Regla 08: Modificación de tareas programadas
- **Técnica MITRE:** T1053 (Scheduled Task/Job)
- **Condición:** Creación o modificación de tarea programada (crontab, schtasks)
- **Ventana de tiempo:** instantánea
- **Severidad:** MEDIUM
- **Archivo:** `rules/regla_08_tarea_programada.py`

## Regla 09: Comportamiento de ransomware (FIM)
- **Técnica MITRE:** T1486 (Data Encrypted for Impact)
- **Condición:** >= 10 archivos renombrados/modificados con extensiones sospechosas (.locked, .encrypted, .cry) en 1 minuto
- **Ventana de tiempo:** 1 min
- **Severidad:** CRITICAL
- **Archivo:** `rules/regla_09_ransomware_fim.py`

## Regla 10: Exfiltración de datos por volumen
- **Técnica MITRE:** T1048 (Exfiltration Over Alternative Protocol)
- **Condición:** >= 500MB de datos enviados desde un host en 10 minutos
- **Ventana de tiempo:** 10 min
- **Severidad:** HIGH
- **Archivo:** `rules/regla_10_exfiltracion_volumen.py`

## Regla 11: Movimiento lateral (login desde host comprometido)
- **Técnica MITRE:** T1021 (Remote Services)
- **Condición:** Login exitoso desde una IP que previamente disparó Regla 01 o Regla 06
- **Ventana de tiempo:** 30 min
- **Severidad:** CRITICAL
- **Archivo:** `rules/regla_11_movimiento_lateral.py`

## Regla 12: Desactivación de antivirus/seguridad
- **Técnica MITRE:** T1562 (Impair Defenses)
- **Condición:** Evento de detención de servicio de seguridad (Windows Defender, firewall, SATRI Agent)
- **Ventana de tiempo:** instantánea
- **Severidad:** CRITICAL
- **Archivo:** `rules/regla_12_desactivacion_seguridad.py`

## Regla 13: DNS tunneling sospechoso
- **Técnica MITRE:** T1572 (Protocol Tunneling)
- **Condición:** >= 50 consultas DNS a subdominios del mismo dominio en 5 minutos, con longitud de subdominio > 30 caracteres
- **Ventana de tiempo:** 5 min
- **Severidad:** HIGH
- **Archivo:** `rules/regla_13_dns_tunneling.py`

## Regla 14: Anomalía de comportamiento UEBA (señal de MIA_ML)
- **Técnica MITRE:** T1078 (Valid Accounts) — uso anómalo de cuentas legítimas
- **Condición:** MIA_ML reporta anomaly_score > umbral configurable (default 0.7) para un evento de login/sesión
- **Ventana de tiempo:** instantánea (basada en el score del modelo)
- **Severidad:** MEDIUM (se eleva en MTA si coincide con otras señales)
- **Archivo:** `rules/regla_14_anomalia_ueba.py`

---

**Estado:** ✅ APROBADO — proceder a implementación de cada regla.
