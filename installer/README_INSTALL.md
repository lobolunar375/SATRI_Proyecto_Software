# 📦 SATRI v2 — Guía de Instalación para Usuarios de Prueba

## Requisitos del Sistema

- Windows 10/11 (64 bits)
- 100 MB de espacio en disco
- Conexión a internet (para reportar telemetría)
- Google Chrome o Microsoft Edge (para la extensión)

---

## Instalación de la App de Escritorio

### Opción A: Instalador (recomendado)
1. Ejecuta `SATRI_Setup_v2.0.0.exe`
2. Sigue el asistente de instalación
3. En la primera ejecución, verás la **pantalla de consentimiento**
4. Lee qué datos se recolectan y qué NO
5. Si aceptas → la protección se activa completa
6. Si rechazas → la protección local sigue activa, pero no se envían reportes

### Opción B: Ejecutable directo
1. Copia `SATRI_Protection.exe` a cualquier carpeta
2. Ejecútalo → aparecerá en la bandeja del sistema (🛡️)

---

## Instalación de la Extensión de Navegador

1. Abre Chrome/Edge
2. Navega a `chrome://extensions/`
3. Activa **"Modo de desarrollador"** (esquina superior derecha)
4. Haz clic en **"Cargar descomprimida"**
5. Selecciona la carpeta `browser_extension/`
6. La extensión aparecerá con el ícono 🛡️

---

## Qué Hace SATRI

| Protección | Qué detecta |
|---|---|
| 🔍 Monitor de procesos | Virus, troyanos, herramientas de hacking |
| 🛡️ Anti-ransomware | Cifrado masivo de archivos |
| 📥 Escáner de descargas | Archivos maliciosos descargados |
| 🔥 Firewall personal | IPs maliciosas conocidas |
| 📡 Detector WiFi | Redes sin cifrado (WPA2/WPA3) |
| 🌐 Extensión web | Certificados SSL inválidos, sitios de phishing |

---

## Tu Privacidad

- ✅ Solo se envía: tipo de amenaza, severidad, fecha/hora
- ❌ NUNCA se envía: páginas visitadas, contraseñas, archivos, capturas de pantalla
- 📋 Puedes ver qué se reportó: clic derecho en el ícono → "Ver reportes"
- ⏸️ Puedes pausar: clic derecho → "Pausar telemetría"
- 🗑️ Puedes desinstalar: Panel de Control → Desinstalar SATRI

---

## Desinstalación

### Desde la app:
- Clic derecho en el ícono de bandeja → "Desinstalar limpiamente"

### Desde Windows:
- Panel de Control → Programas → Desinstalar SATRI Endpoint Protection

La desinstalación elimina:
- Todos los archivos de la app
- Todos los datos locales (configuración, historial de eventos)
- Todas las reglas de firewall creadas por SATRI
- No deja procesos ni datos residuales

---

## Soporte

Si tienes algún problema, contacta al administrador del proyecto.
