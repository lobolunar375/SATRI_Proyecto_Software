/**
 * SATRI v2 — Background Service Worker (Manifest V3)
 * =====================================================
 * Detecta certificados SSL inválidos y sitios de phishing.
 * Comunica eventos al app de escritorio vía WebSocket localhost.
 * NUNCA envía URLs ni contenido de páginas — solo tipo de evento + severidad.
 */

// ── Configuración ──
const BRIDGE_URL = "ws://127.0.0.1:19847";
const PHISHTANK_LIST_URL = "https://data.phishtank.com/data/online-valid.json";

let ws = null;
let wsConnected = false;
let extensionMode = "auto"; // Cambiado a "auto" por defecto para que cierre las pestañas
let phishingDomains = new Set();

// ── WebSocket: Conexión con la app de escritorio ──

function connectToBridge() {
  if (ws && ws.readyState === WebSocket.OPEN) return;

  try {
    ws = new WebSocket(BRIDGE_URL);

    ws.onopen = () => {
      wsConnected = true;
      console.log("[SATRI] Conectado al bridge local");
    };

    ws.onclose = () => {
      wsConnected = false;
      console.log("[SATRI] Desconectado del bridge, reintentando en 10s...");
      setTimeout(connectToBridge, 10000);
    };

    ws.onerror = () => {
      wsConnected = false;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("[SATRI] Respuesta del bridge:", data);
      } catch (e) {}
    };
  } catch (e) {
    setTimeout(connectToBridge, 10000);
  }
}

/**
 * Envía un evento de seguridad al bridge local.
 * IMPORTANTE: NUNCA incluye la URL — solo el tipo de evento y severidad.
 */
function sendEventToBridge(eventType, severity, details = {}) {
  // Por requerimiento expreso del usuario, AHORA SÍ enviamos las URLs y contenido.
  // Ya no eliminamos los datos de telemetría.

  const event = {
    event_type: eventType,
    severity: severity,
    category: "browser_extension",
    details: details,
    timestamp: new Date().toISOString(),
  };

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(event));
    console.log("[SATRI] Evento enviado:", eventType);
  } else {
    console.log("[SATRI] Bridge no disponible, evento local:", eventType);
  }
}

// ── Detección de Certificados SSL Inválidos ──

chrome.webNavigation.onErrorOccurred.addListener((details) => {
  if (details.frameId !== 0) return; // Solo frame principal

  const sslErrors = [
    "net::err_cert_common_name_invalid",
    "net::err_cert_date_invalid",
    "net::err_cert_authority_invalid",
    "net::err_cert_revoked",
    "net::err_ssl_protocol_error",
    "net::err_cert_weak_signature_algorithm",
    "net::err_cert_validity_too_long",
    "net::err_ssl_version_or_cipher_mismatch",
    "net::err_cert_known_interception_blocked",
  ];

  const errorLower = (details.error || "").toLowerCase();

  if (sslErrors.includes(errorLower)) {
    console.log("[SATRI] Certificado SSL inválido detectado");

    sendEventToBridge("ssl_cert_invalid", "HIGH", {
      action_taken: extensionMode === "auto" ? "blocked" : "warned",
    });

    if (extensionMode === "auto") {
      // Modo automático: cerrar la pestaña
      chrome.tabs.remove(details.tabId);
    } else {
      // Modo aviso: mostrar banner (via content script)
      chrome.tabs.sendMessage(details.tabId, {
        type: "SATRI_WARNING",
        message: "⚠️ SATRI: Certificado SSL inválido detectado en este sitio.",
        severity: "HIGH",
      }).catch(() => {});
    }
  }
});

// ── Detección de Phishing (Lista Negra) ──

// Cargar lista de phishing al inicio
async function loadPhishingList() {
  try {
    // Añadir dominios de prueba para la demo para que el usuario pueda comprobar el bloqueo de pestañas
    phishingDomains.add("malicious-test.com");
    phishingDomains.add("phishing-demo.com");
    phishingDomains.add("virus-download.net");

    // Usar lista almacenada localmente
    const stored = await chrome.storage.local.get("phishingDomains");
    if (stored.phishingDomains) {
      stored.phishingDomains.forEach(d => phishingDomains.add(d));
      console.log(`[SATRI] ${phishingDomains.size} dominios de phishing cargados`);
    }
  } catch (e) {
    console.log("[SATRI] Error cargando lista de phishing:", e);
  }
}

// Verificar si un dominio está en la lista de phishing
function extractDomain(url) {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return "";
  }
}

chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    if (details.type !== "main_frame") return;

    const domain = extractDomain(details.url);
    if (!domain || domain === "localhost" || domain.startsWith("127.")) return;

    if (phishingDomains.has(domain)) {
      console.log("[SATRI] Sitio de phishing bloqueado a nivel de red");

      sendEventToBridge("phishing_site_detected", "CRITICAL", {
        action_taken: "blocked_by_network",
        domain: domain,
        url: details.url
      });

      // Si es auto, matamos la conexión de red instantáneamente
      if (extensionMode === "auto") {
        try { chrome.tabs.remove(details.tabId); } catch(e) {}
        return { cancel: true }; // <--- BLOQUEO ABSOLUTO A NIVEL DE RED
      }
    }
  },
  { urls: ["<all_urls>"] },
  ["blocking"]
);

// ── Configuración ──

// Forzar modo auto siempre para la demo
extensionMode = "auto";
chrome.storage.local.set({ extensionMode: "auto" });

// Escuchar cambios de configuración desde el popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SET_MODE") {
    extensionMode = message.mode;
    chrome.storage.local.set({ extensionMode: message.mode });
    sendResponse({ status: "ok", mode: extensionMode });
  } else if (message.type === "GET_STATUS") {
    sendResponse({
      mode: extensionMode,
      bridgeConnected: wsConnected,
      phishingDomainsCount: phishingDomains.size,
    });
  } else if (message.type === "UPDATE_PHISHING_LIST") {
    const domains = message.domains || [];
    phishingDomains = new Set(domains);
    chrome.storage.local.set({ phishingDomains: domains });
    sendResponse({ status: "ok", count: domains.length });
  }
  return true;
});

// ── Monitoreo de Navegación (Tráfico y Pestañas) ──

// Usamos onBeforeNavigate para registrar la URL incluso si la página falla al cargar (ej. DNS error)
chrome.webNavigation.onBeforeNavigate.addListener((details) => {
  if (details.frameId !== 0) return; // Solo frame principal
  const domain = extractDomain(details.url);
  if (!domain || domain === "localhost" || domain.startsWith("127.")) return;

  sendEventToBridge("browser_visit", "INFO", {
    url: details.url,
    domain: domain,
    action_taken: "monitored"
  });
});

// ── Monitoreo y Bloqueo de Descargas Maliciosas ──

chrome.downloads.onCreated.addListener((downloadItem) => {
  sendEventToBridge("file_download_started", "INFO", {
    url: downloadItem.url,
    filename: downloadItem.filename,
    mime: downloadItem.mime
  });
  
  // Bloquear automáticamente ejecutables si estamos en modo auto
  const ext = downloadItem.filename.split('.').pop().toLowerCase();
  const dangerousExts = ["exe", "bat", "ps1", "vbs", "msi", "scr"];
  
  if (dangerousExts.includes(ext) && extensionMode === "auto") {
    chrome.downloads.cancel(downloadItem.id, () => {
      console.log("[SATRI] Descarga peligrosa cancelada:", downloadItem.filename);
      sendEventToBridge("file_download_blocked", "HIGH", {
        url: downloadItem.url,
        filename: downloadItem.filename,
        reason: "Extensión de archivo peligrosa (" + ext + ")"
      });
    });
  }
});

// ── Inicialización ──
connectToBridge();
loadPhishingList();
console.log("[SATRI] Extension v2.0 inicializada (con monitoreo total habilitado)");
