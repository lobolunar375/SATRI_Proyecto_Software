// Content Script para analizar el DOM de páginas sospechosas

function checkPhishingIndicators() {
    // Escaneo local de indicadores de phishing o formularios inseguros
    const passwordFields = document.querySelectorAll('input[type="password"]');
    
    // Si la página no es HTTPS pero pide contraseñas
    if (window.location.protocol !== 'https:' && passwordFields.length > 0) {
        chrome.runtime.sendMessage({
            action: "handleInsecureTab",
            reason: "HTTP protocol used with password fields."
        });
        
        // Alerta al usuario en el DOM
        const banner = document.createElement('div');
        banner.style.backgroundColor = 'red';
        banner.style.color = 'white';
        banner.style.padding = '10px';
        banner.style.position = 'fixed';
        banner.style.top = '0';
        banner.style.width = '100%';
        banner.style.zIndex = '999999';
        banner.innerText = 'SATRI ALERTA: Esta página solicita contraseñas de forma insegura. NO INGRESE DATOS.';
        document.body.prepend(banner);
    }
}

// Ejecutar revisión al cargar
window.onload = checkPhishingIndicators;
