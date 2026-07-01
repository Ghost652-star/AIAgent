from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from bugdoctor.tools.base import Tool, ToolResult

MAX_TIMEOUT = 120
MAX_OUTPUT_CHARS = 8000


class RunCommandParams(BaseModel):
    command: str = Field(description="Shell command to run, e.g. 'python main.py' or 'python --version'")
    timeout: int = Field(default=60, description="Timeout in seconds (max 120)")


class RunCommandTool(Tool):
    name = "run_command"
    description = (
        "Run a shell command inside the project directory to reproduce a bug, "
        "check runtime behavior, or verify a hypothesis. "
        "Use after reading code when you need to confirm what actually happens at runtime. "
        "Returns stdout, stderr, and exit code."
    )
    params_model = RunCommandParams
    risk = "run"

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        params = RunCommandParams.model_validate(arguments)
        timeout = min(max(params.timeout, 1), MAX_TIMEOUT)
        cwd = self._project_root.resolve()

        try:
            proc = await asyncio.create_subprocess_shell(
                params.command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult(
                f"Error: command timed out after {timeout}s",
                is_error=True,
            )
        except Exception as exc:
            return ToolResult(f"Error executing command: {exc}", is_error=True)

        parts: list[str] = [f"exit_code: {proc.returncode}"]
        if stdout:
            parts.append(f"STDOUT:\n{stdout.decode(errors='replace')}")
        if stderr:
            parts.append(f"STDERR:\n{stderr.decode(errors='replace')}")
        if len(parts) == 1:
            parts.append("(no output)")

        output = "\n".join(parts)
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n(truncated output)"

        return ToolResult(output, is_error=proc.returncode != 0)
