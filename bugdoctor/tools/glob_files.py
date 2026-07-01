from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from bugdoctor.tools.base import Tool, ToolResult
from bugdoctor.tools.sandbox import resolve_in_project, should_skip_path

MAX_RESULTS = 200


class GlobFilesParams(BaseModel):
    pattern: str = Field(description="Glob pattern, e.g. '**/*.py' or '**/*.java'")
    path: str = Field(default=".", description="Search root relative to project root")


class GlobFilesTool(Tool):
    name = "glob_files"
    description = (
        "Find files matching a glob pattern inside the project. "
        "Use when you need project structure or a class of files "
        "(e.g. all Python sources, all tests) — especially when the traceback "
        "does not list every relevant file. Read-only, non-destructive."
    )
    params_model = GlobFilesParams
    risk = "read"

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        params = GlobFilesParams.model_validate(arguments)
        base, err = resolve_in_project(self._project_root, params.path)
        if base is None:
            return ToolResult(err, is_error=True)
        if not base.exists():
            return ToolResult(f"Error: path not found: {params.path}", is_error=True)
        if not base.is_dir():
            return ToolResult(f"Error: not a directory: {params.path}", is_error=True)

        try:
            matches = sorted(
                str(p.relative_to(base))
                for p in base.glob(params.pattern)
                if p.is_file() and not should_skip_path(p)
            )
        except Exception as exc:
            return ToolResult(f"Error: {exc}", is_error=True)

        if not matches:
            return ToolResult("No files matched the pattern.")

        total = len(matches)
        if total > MAX_RESULTS:
            matches = matches[:MAX_RESULTS]
            body = "\n".join(matches)
            return ToolResult(f"{body}\n(truncated, showing first {MAX_RESULTS} of {total})")

        return ToolResult("\n".join(matches))
