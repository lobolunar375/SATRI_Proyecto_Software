"""
Regla 13: DNS tunneling sospechoso
Técnica MITRE: T1572 (Protocol Tunneling)
Condición: >= 50 consultas DNS al mismo dominio en 5 min, subdominio > 30 chars
"""
from time_window_engine import increment_counter

RULE_NAME = "DNS_TUNNELING"
MITRE_ID = "T1572"
THRESHOLD = 50
WINDOW_SECONDS = 300
MIN_SUBDOMAIN_LENGTH = 30


def evaluate(event: dict) -> dict | None:
    event_type = event.get("event_type", "").lower()

    if event_type not in ["dns_query", "dns_request"]:
        return None

    domain = event.get("domain", event.get("dns_name", "")).lower()
    src_ip = event.get("src_ip")

    if not domain or not src_ip:
        return None

    parts = domain.split(".")
    if len(parts) < 3:
        return None

    subdomain = parts[0]
    base_domain = ".".join(parts[-2:])

    if len(subdomain) >= MIN_SUBDOMAIN_LENGTH:
        key = f"mcor:r13:dns:{src_ip}:{base_domain}"
        count = increment_counter(key, WINDOW_SECONDS)

        if count >= THRESHOLD:
            return {
                "rule": RULE_NAME,
                "mitre": MITRE_ID,
                "severity": "HIGH",
                "reason": f"DNS Tunneling sospechoso: {count} queries a {base_domain} con subdominios largos (>{MIN_SUBDOMAIN_LENGTH} chars) desde {src_ip}",
                "src_ip": src_ip,
                "domain": base_domain,
                "count": count
            }
    return None

