from __future__ import annotations

from typing import Any

from mcp import types as mcp_types
from pydantic import BaseModel, create_model

from bugdoctor.mcp.client import MCPClient
from bugdoctor.tools.base import Tool, ToolResult


def _build_params_model(tool_name: str, input_schema: dict[str, Any]) -> type[BaseModel]:
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    field_definitions: dict[str, Any] = {}
    for name, prop in properties.items():
        py_type = _json_type_to_python(prop.get("type", "string"))
        if name in required:
            field_definitions[name] = (py_type, ...)
        else:
            field_definitions[name] = (py_type | None, None)

    safe_name = tool_name.replace("-", "_")
    return create_model(f"MCP_{safe_name}_Params", **field_definitions)


def _json_type_to_python(json_type: str) -> type:
    mapping: dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    return mapping.get(json_type, str)


def _extract_text(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        if isinstance(block, mcp_types.TextContent):
            parts.append(block.text)
        elif isinstance(block, mcp_types.ImageContent):
            parts.append(f"[image: {block.mimeType}]")
        elif isinstance(block, mcp_types.EmbeddedResource):
            resource = block.resource
            if hasattr(resource, "text"):
                parts.append(resource.text)
            else:
                parts.append(f"[binary resource: {resource.uri}]")
    return "\n".join(parts) if parts else "(no output)"


class MCPToolWrapper(Tool):
    def __init__(
        self,
        server_name: str,
        tool_def: mcp_types.Tool,
        client: MCPClient,
    ) -> None:
        self._server_name = server_name
        self._tool_def = tool_def
        self._client = client
        self.name = f"mcp_{server_name}_{tool_def.name}"
        self.description = tool_def.description or tool_def.name
        self.risk = "read"
        schema = tool_def.inputSchema if isinstance(tool_def.inputSchema, dict) else {}
        self.params_model = _build_params_model(tool_def.name, schema)

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        if not self._client.is_alive:
            try:
                await self._client.connect()
            except Exception as e:
                return ToolResult(
                    f"MCP server '{self._server_name}' reconnect failed: {e}",
                    is_error=True,
                )

        if self.params_model:
            params = self.params_model.model_validate(arguments)
            payload = params.model_dump(exclude_none=True)
        else:
            payload = arguments

        try:
            result = await self._client.call_tool(self._tool_def.name, payload)
        except Exception as e:
            self._client._alive = False
            return ToolResult(f"MCP tool call failed: {e}", is_error=True)

        text = _extract_text(result.content)
        return ToolResult(text, is_error=bool(result.isError))
