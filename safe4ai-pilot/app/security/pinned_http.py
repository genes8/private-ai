from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

import httpcore
import httpx


def _hostname_for(url: str) -> str:
    hostname = urlparse(url).hostname
    if not hostname:
        raise ValueError("Pinned HTTP URL must include a hostname")
    return hostname.lower()


class _PinnedNetworkBackend(httpcore.NetworkBackend):
    def __init__(self, hostname: str, resolved_ip: str) -> None:
        self._hostname = hostname.lower()
        self._resolved_ip = resolved_ip
        self._delegate = httpcore.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.NetworkStream:
        target = self._resolved_ip if host.lower() == self._hostname else host
        return self._delegate.connect_tcp(
            target,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.NetworkStream:
        return self._delegate.connect_unix_socket(
            path,
            timeout=timeout,
            socket_options=socket_options,
        )

    def sleep(self, seconds: float) -> None:
        self._delegate.sleep(seconds)


class _PinnedAsyncNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, hostname: str, resolved_ip: str) -> None:
        self._hostname = hostname.lower()
        self._resolved_ip = resolved_ip
        self._delegate = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        target = self._resolved_ip if host.lower() == self._hostname else host
        return await self._delegate.connect_tcp(
            target,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._delegate.connect_unix_socket(
            path,
            timeout=timeout,
            socket_options=socket_options,
        )

    async def sleep(self, seconds: float) -> None:
        await self._delegate.sleep(seconds)


class PinnedHTTPTransport(httpx.HTTPTransport):
    def __init__(self, url: str, resolved_ip: str) -> None:
        super().__init__()
        self._pool = httpcore.ConnectionPool(
            network_backend=_PinnedNetworkBackend(_hostname_for(url), resolved_ip)
        )


class PinnedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    def __init__(self, url: str, resolved_ip: str) -> None:
        super().__init__()
        self._pool = httpcore.AsyncConnectionPool(
            network_backend=_PinnedAsyncNetworkBackend(_hostname_for(url), resolved_ip)
        )


def create_pinned_transport(url: str, resolved_ip: str) -> httpx.HTTPTransport:
    return PinnedHTTPTransport(url, resolved_ip)


def create_pinned_async_transport(url: str, resolved_ip: str) -> httpx.AsyncHTTPTransport:
    return PinnedAsyncHTTPTransport(url, resolved_ip)
