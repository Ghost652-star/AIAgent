from __future__ import annotations

import logging

from bugdoctor.mcp.client import MCPClient, MCPServerConfig
from bugdoctor.mcp.tool_wrapper import MCPToolWrapper
from bugdoctor.tools.base import ToolRegistry

log = logging.getLogger(__name__)


class MCPManager:
    def __init__(self) -> None:
        self._configs: dict[str, MCPServerConfig] = {}
        self._clients: dict[str, MCPClient] = {}

    def load_configs(self, configs: list[MCPServerConfig]) -> None:
        for cfg in configs:
            self._configs[cfg.name] = cfg

    async def register_all_tools(self, registry: ToolRegistry) -> list[str]:
        errors: list[str] = []
        for name, config in self._configs.items():
            try:
                client = MCPClient(config)
                await client.connect()
                self._clients[name] = client

                tools = await client.list_tools()
                for tool_def in tools:
                    wrapper = MCPToolWrapper(name, tool_def, client)
                    registry.register(wrapper)
                    log.info("Registered MCP tool: %s", wrapper.name)
            except Exception as e:
                msg = f"MCP server '{name}': {e}"
                log.warning(msg)
                errors.append(msg)
        return errors

    async def shutdown(self) -> None:
        for client in self._clients.values():
            try:
                await client.close()
            except Exception:
                log.debug("Error closing MCP client", exc_info=True)
        self._clients.clear()
