"""URL validator: block SSRF attempts by rejecting private/reserved IP ranges."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique-local
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]

_ALLOWED_SCHEMES = {"http", "https"}


def _resolve_and_check(hostname: str) -> str:
    """Resolve *hostname* and raise HTTPException(422) if any resolved IP is private.

    Returns the first resolved IP string so the caller can pin it in the transport,
    preventing DNS rebinding between validation and the actual request.
    """
    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise HTTPException(status_code=422, detail=f"Cannot resolve hostname '{hostname}'")

    first_ip: str | None = None
    for _family, _type, _proto, _canonname, sockaddr in resolved:
        ip = ipaddress.ip_address(sockaddr[0])
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise HTTPException(
                    status_code=422,
                    detail="Provider URL resolves to a private/reserved IP address",
                )
        if first_ip is None:
            first_ip = sockaddr[0]

    if first_ip is None:
        raise HTTPException(status_code=422, detail=f"Cannot resolve hostname '{hostname}'")
    return first_ip


def validate_provider_url(url: str) -> tuple[str, str]:
    """Validate a provider base URL against SSRF attacks.

    Returns (cleaned_url, resolved_ip). The caller MUST use *resolved_ip* as the
    connection target so the hostname cannot be re-resolved (DNS rebinding prevention).
    Raises HTTPException(422) if the URL targets a private/reserved address.
    """
    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(
            status_code=422,
            detail=f"URL scheme '{parsed.scheme}' is not allowed; use http or https",
        )

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=422, detail="URL must include a hostname")

    resolved_ip = _resolve_and_check(hostname)
    return url.rstrip("/"), resolved_ip
