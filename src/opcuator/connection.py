from __future__ import annotations

import asyncio
from dataclasses import dataclass

from asyncua import Client

from .config import settings
from .opcua_browser import (
    OpcUaBrowseError,
    configure_client,
    get_configured_endpoint,
)


@dataclass
class ConnectionState:
    connected: bool
    endpoint: str | None
    last_error: str | None


class OpcUaConnectionManager:
    def __init__(self) -> None:
        self._client: Client | None = None
        self._endpoint: str | None = None
        self._last_error: str | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> ConnectionState:
        async with self._lock:
            if self._client is not None:
                return self.status()

            endpoint = get_configured_endpoint()
            client = Client(url=endpoint, timeout=settings.opcua_request_timeout)
            try:
                await configure_client(client)
                await client.connect()
            except Exception as exc:
                self._last_error = str(exc)
                try:
                    await client.disconnect()
                except Exception:
                    pass
                raise

            self._client = client
            self._endpoint = endpoint
            self._last_error = None
            return self.status()

    async def disconnect(self) -> ConnectionState:
        async with self._lock:
            client = self._client
            self._client = None
            self._endpoint = None
            if client is not None:
                await client.disconnect()
            return self.status()

    async def get_client(self) -> Client:
        if self._client is None:
            await self.connect()
        if self._client is None:
            raise OpcUaBrowseError("OPC UA client is not connected.")
        return self._client

    async def reset_after_error(self, error: Exception) -> None:
        self._last_error = str(error)
        await self.disconnect()

    def status(self) -> ConnectionState:
        return ConnectionState(
            connected=self._client is not None,
            endpoint=self._endpoint,
            last_error=self._last_error,
        )


connection_manager = OpcUaConnectionManager()
