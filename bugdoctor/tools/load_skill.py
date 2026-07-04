from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from bugdoctor.tools.base import Tool, ToolResult

if TYPE_CHECKING:
    from bugdoctor.skills.manager import SkillManager


class LoadSkillParams(BaseModel):
    name: str = Field(description="Skill name from the catalog (e.g. parse-stack-trace).")


class LoadSkillTool(Tool):
    name = "load_skill"
    description = (
        "Load and activate a Skill by name. The Skill SOP is injected into context "
        "and tool access may be restricted per allowedTools. Call when the user's "
        "request matches a Skill description in the catalog."
    )
    params_model = LoadSkillParams
    risk = "read"

    def __init__(self) -> None:
        self._manager: SkillManager | None = None

    def set_manager(self, manager: SkillManager) -> None:
        self._manager = manager

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        params = LoadSkillParams.model_validate(arguments)
        if self._manager is None:
            return ToolResult("Error: load_skill not initialized", is_error=True)

        ok, msg = self._manager.activate(params.name)
        return ToolResult(msg, is_error=not ok)
