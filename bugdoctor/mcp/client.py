from __future__ import annotations

import logging
import os
import re
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

import httpx
from mcp import ClientSession, types
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

log = logging.getLogger(__name__)

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def resolve_env_vars(value: str) -> str:
    return _ENV_VAR_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)


def build_child_env(declared_env: dict[str, str] | None) -> dict[str, str]:
    env: dict[str, str] = {}
    path = os.environ.get("PATH", "")
    if path:
        env["PATH"] = path
    for key, value in (declared_env or {}).items():
        env[key] = resolve_env_vars(value)
    return env


@dataclass
class MCPServerConfig:
    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)

    @property
    def is_stdio(self) -> bool:
        return self.command is not None


class MCPClient:
    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self.name = config.name
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None
        self._alive = False

    @property
    def is_alive(self) -> bool:
        return self._alive

    async def connect(self) -> None:
        if self._alive:
            return

        self._stack = AsyncExitStack()
        await self._stack.__aenter__()

        try:
            if self.config.is_stdio:
                read, write = await self._connect_stdio()
            else:
                read, write = await self._connect_http()

            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._session = session
            self._alive = True
            log.info("MCP server '%s' connected", self.name)
        except Exception:
            await self._cleanup_stack()
            raise

    async def _connect_stdio(self) -> tuple[Any, Any]:
        assert self._stack is not None
        assert self.config.command is not None

        params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=build_child_env(self.config.env),
        )
        devnull = open(os.devnull, "w")
        self._stack.callback(devnull.close)
        read, write = await self._stack.enter_async_context(
            stdio_client(params, errlog=devnull)
        )
        return read, write

    async def _connect_http(self) -> tuple[Any, Any]:
        assert self._stack is not None
        assert self.config.url is not None

        resolved_headers = {
            k: resolve_env_vars(v) for k, v in self.config.headers.items()
        }
        http_client = httpx.AsyncClient(headers=resolved_headers, follow_redirects=True)
        await self._stack.enter_async_context(http_client)

        result = await self._stack.enter_async_context(
            streamable_http_client(self.config.url, http_client=http_client)
        )
        return result[0], result[1]

    async def list_tools(self) -> list[types.Tool]:
        assert self._session is not None
        result = await self._session.list_tools()
        return list(result.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        assert self._session is not None
        return await self._session.call_tool(name, arguments)

    async def close(self) -> None:
        self._alive = False
        self._session = None
        await self._cleanup_stack()

    async def _cleanup_stack(self) -> None:
        if self._stack is not None:
            try:
                await self._stack.__aexit__(None, None, None)
            except Exception:
                log.debug("Error closing MCP stack for '%s'", self.name, exc_info=True)
            self._stack = None
