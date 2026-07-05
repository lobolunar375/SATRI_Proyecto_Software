import re
from dataclasses import dataclass
from ipaddress import ip_address, AddressValueError

@dataclass
class IoC:
    type: str  # ip, hash_sha256, hash_md5, domain, url, email, btc_address
    value: str

PATTERNS = {
    "hash_sha256": re.compile(r"\b[0-9a-fA-F]{64}\b"),
    "hash_md5": re.compile(r"\b[0-9a-fA-F]{32}\b"),
    "hash_sha1": re.compile(r"\b[0-9a-fA-F]{40}\b"),
    "url": re.compile(r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[-\w%_.~+&?=#]*)?"),
    "domain": re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "ip": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "btc_address": re.compile(r"\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b"),
}

# IPs RFC1918 (privadas) - se descartan
PRIVATE_RANGES = [
    re.compile(r"^10\."),
    re.compile(r"^192\.168\."),
    re.compile(r"^172\.(?:1[6-9]|2\d|3[01])\."),
    re.compile(r"^127\."),
]

def is_private_ip(ip: str) -> bool:
    try:
        # Validación más estricta usando ipaddress
        ip_obj = ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback:
            return True
    except AddressValueError:
        pass
        
    return any(p.match(ip) for p in PRIVATE_RANGES)

def extract_iocs(text: str) -> list[IoC]:
    iocs = []
    seen = set()
    for ioc_type, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(0)
            if ioc_type == "ip" and is_private_ip(value):
                continue # Descartar IPs privadas
            key = f"{ioc_type}:{value}"
            if key not in seen:
                seen.add(key)
                iocs.append(IoC(type=ioc_type, value=value))
    return iocs
