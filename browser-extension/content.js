/**
 * SATRI v2 — Content Script
 * Muestra banners de advertencia inyectados en la página.
 */

// Escuchar mensajes del background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SATRI_WARNING") {
    showWarningBanner(message.message, message.severity);
    sendResponse({ status: "shown" });
  }
  return true;
});

function showWarningBanner(text, severity) {
  // Evitar duplicados
  if (document.getElementById("satri-warning-banner")) return;

  const banner = document.createElement("div");
  banner.id = "satri-warning-banner";

  const bgColor = severity === "CRITICAL" ? "#d32f2f" : "#f57c00";

  banner.style.cssText = `
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 100% !important;
    z-index: 2147483647 !important;
    background: ${bgColor} !important;
    color: white !important;
    padding: 12px 20px !important;
    font-family: 'Segoe UI', Arial, sans-serif !important;
    font-size: 14px !important;
    font-weight: bold !important;
    text-align: center !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 15px !important;
  `;

  const textSpan = document.createElement("span");
  textSpan.textContent = text;

  const closeBtn = document.createElement("button");
  closeBtn.textContent = "✕ Cerrar";
  closeBtn.style.cssText = `
    background: rgba(255,255,255,0.2) !important;
    border: 1px solid white !important;
    color: white !important;
    padding: 5px 12px !important;
    border-radius: 4px !important;
    cursor: pointer !important;
    font-size: 12px !important;
  `;
  closeBtn.onclick = () => banner.remove();

  banner.appendChild(textSpan);
  banner.appendChild(closeBtn);
  document.body.prepend(banner);

  // Auto-remover después de 15 segundos
  setTimeout(() => {
    if (banner.parentNode) banner.remove();
  }, 15000);
}
