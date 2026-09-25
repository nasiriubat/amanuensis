"""SSRF guard for outbound fetches of user/third-party-supplied URLs.

The literature scan adopts `pdf_url`s that come from external indexes (OpenAlex), so a
crafted record could point the server at an internal address (127.0.0.1, cloud metadata
at 169.254.169.254, another container on the Docker network). Before fetching such a URL,
resolve its host and refuse any address that is not publicly routable — and re-check every
redirect hop, since a public URL can 302 to an internal one.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    pass


def assert_public_url(url: str) -> None:
    """Raise UnsafeUrlError unless `url` is http(s) and every resolved IP is publicly routable."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError("Only http and https URLs can be fetched.")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL has no host.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise UnsafeUrlError(f"Could not resolve host: {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        blocked = ip.is_private or ip.is_loopback or ip.is_link_local
        blocked = blocked or ip.is_reserved or ip.is_multicast or ip.is_unspecified
        if blocked:
            raise UnsafeUrlError(f"Refusing to fetch a non-public address ({ip}).")
