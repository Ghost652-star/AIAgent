from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from bugdoctor.tools.base import Tool, ToolResult
from bugdoctor.tools.sandbox import resolve_in_project

BUGDOCTOR_SUBDIR = ".bugdoctor"


class WriteFileParams(BaseModel):
    file_path: str = Field(
        description="Path relative to project root. Must be under .bugdoctor/ (e.g. .bugdoctor/module-map.md).",
    )
    content: str = Field(description="Full file content to write (creates or overwrites).")


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Write or overwrite a file under .bugdoctor/ in the diagnosis workspace. "
        "Use for module-map.md and other BugDoctor artifacts — not for editing source code "
        "(use edit_file for source). Parent directories are created if needed."
    )
    params_model = WriteFileParams
    risk = "write"

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def _is_allowed_path(self, resolved: Path) -> bool:
        root = self._project_root.resolve()
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            return False
        parts = rel.parts
        return len(parts) >= 1 and parts[0] == BUGDOCTOR_SUBDIR

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        params = WriteFileParams.model_validate(arguments)
        resolved, err = resolve_in_project(self._project_root, params.file_path)
        if resolved is None:
            return ToolResult(err, is_error=True)
        if not self._is_allowed_path(resolved):
            return ToolResult(
                f"Error: write_file only allows paths under {BUGDOCTOR_SUBDIR}/",
                is_error=True,
            )

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(params.content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(f"Error writing file: {exc}", is_error=True)

        rel = resolved.relative_to(self._project_root.resolve())
        return ToolResult(f"Successfully wrote {rel}")
