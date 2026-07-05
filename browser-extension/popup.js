/**
 * SATRI v2 — Popup Script
 * Maneja la UI del popup de configuración de la extensión.
 */

document.addEventListener("DOMContentLoaded", () => {
  const bridgeStatus = document.getElementById("bridge-status");
  const phishingCount = document.getElementById("phishing-count");
  const currentMode = document.getElementById("current-mode");
  const modeWarn = document.getElementById("mode-warn");
  const modeAuto = document.getElementById("mode-auto");

  // Obtener estado actual del background
  chrome.runtime.sendMessage({ type: "GET_STATUS" }, (response) => {
    if (chrome.runtime.lastError || !response) {
      bridgeStatus.textContent = "❌ Error";
      bridgeStatus.className = "status-value disconnected";
      return;
    }

    // Estado del bridge
    if (response.bridgeConnected) {
      bridgeStatus.textContent = "🟢 Conectada";
      bridgeStatus.className = "status-value connected";
    } else {
      bridgeStatus.textContent = "🔴 Desconectada";
      bridgeStatus.className = "status-value disconnected";
    }

    // Conteo de phishing
    phishingCount.textContent = `${response.phishingDomainsCount || 0} cargados`;

    // Modo actual
    if (response.mode === "auto") {
      modeAuto.checked = true;
      currentMode.textContent = "Automático";
    } else {
      modeWarn.checked = true;
      currentMode.textContent = "Aviso";
    }
  });

  // Cambio de modo
  modeWarn.addEventListener("change", () => {
    if (modeWarn.checked) {
      setMode("warn");
      currentMode.textContent = "Aviso";
    }
  });

  modeAuto.addEventListener("change", () => {
    if (modeAuto.checked) {
      setMode("auto");
      currentMode.textContent = "Automático";
    }
  });

  function setMode(mode) {
    chrome.runtime.sendMessage({ type: "SET_MODE", mode: mode }, (response) => {
      console.log("[SATRI] Modo cambiado a:", mode);
    });
  }
});
