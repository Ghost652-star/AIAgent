from __future__ import annotations

from bugdoctor.conversation.manager import ConversationManager
from bugdoctor.skills.loader import SkillLoader
from bugdoctor.skills.parser import SkillDef


def build_skill_catalog_section(catalog: list[tuple[str, str]]) -> str:
    if not catalog:
        return ""
    lines = [
        "The following Skills are available (name: description):",
        "",
    ]
    for name, desc in catalog:
        lines.append(f"- **{name}**: {desc}")
    lines.extend(
        [
            "",
            "If the user's request matches a Skill description, call `load_skill` with that name.",
            "If none match, proceed with ReAct and tools directly.",
            "You may load another Skill later when the task phase changes (e.g. apply-fix).",
        ]
    )
    return "\n".join(lines)


class SkillManager:
    """激活 Skill、注入 SOP、维护 allowedTools 并集。"""

    ALWAYS_TOOLS = frozenset({"load_skill"})

    def __init__(
        self,
        loader: SkillLoader,
        conversation: ConversationManager,
    ) -> None:
        self._loader = loader
        self._conversation = conversation
        self._active: dict[str, SkillDef] = {}

    @property
    def active_skills(self) -> dict[str, SkillDef]:
        return dict(self._active)

    def allowed_tool_names(self, all_tool_names: list[str]) -> set[str] | None:
        """无激活 Skill 时不限制；有激活 Skill 时返回并集 + load_skill。"""
        if not self._active:
            return None

        registry = set(all_tool_names)
        allowed: set[str] = set(self.ALWAYS_TOOLS)

        for skill in self._active.values():
            mcp_server_prefixes: set[str] = set()
            for name in skill.allowed_tools:
                if name in registry:
                    allowed.add(name)
                elif name.startswith("mcp_"):
                    parts = name.split("_", 2)
                    if len(parts) >= 2:
                        mcp_server_prefixes.add(f"mcp_{parts[1]}_")

            for t in all_tool_names:
                for prefix in mcp_server_prefixes:
                    if t.startswith(prefix):
                        allowed.add(t)

        return allowed

    def build_active_skills_section(self) -> str:
        """已激活 Skill 的 SOP — 合并进 system prompt（mewcode 做法），不在 tool 批次中间插 user 消息。"""
        if not self._active:
            return ""
        parts = ["## Active Skills", ""]
        for skill in self._active.values():
            tools_note = ", ".join(skill.allowed_tools) if skill.allowed_tools else "(all tools)"
            parts.append(f"### Skill: {skill.name}")
            parts.append(f"Allowed tools: {tools_note}")
            parts.append("")
            parts.append(skill.prompt_body.strip())
            parts.append("")
        return "\n".join(parts).rstrip()

    def activate(self, name: str) -> tuple[bool, str]:
        skill = self._loader.get(name)
        if skill is None:
            names = ", ".join(n for n, _ in self._loader.get_catalog())
            return False, f"Error: unknown skill '{name}'. Available: {names}"

        self._active[name] = skill
        return True, (
            f"Skill '{skill.name}' activated. "
            f"SOP is now in system prompt under Active Skills. "
            f"Allowed tools: {', '.join(skill.allowed_tools) if skill.allowed_tools else 'all'}."
        )
