from __future__ import annotations

import logging
from pathlib import Path

from bugdoctor.skills.parser import SkillDef, SkillParseError, parse_skill_file
from bugdoctor.skills.paths import agent_skills_dir

log = logging.getLogger(__name__)


class SkillLoader:
    """从 {agent_data_root}/.bugdoctor/skills/ 扫描 Skill（与 memory、sessions 同级）。"""

    def __init__(self, agent_data_root: Path) -> None:
        self._agent_data_root = agent_data_root.resolve()
        self._skills_dir = agent_skills_dir(self._agent_data_root)
        self._skills: dict[str, SkillDef] = {}

    @property
    def skills_dir(self) -> Path:
        return self._skills_dir

    def load_all(self) -> dict[str, SkillDef]:
        self._skills_dir.mkdir(parents=True, exist_ok=True)

        seen: dict[str, SkillDef] = {}
        for skill in self._scan_directory(self._skills_dir):
            if skill.name in seen:
                log.warning("Duplicate skill name '%s', later file wins", skill.name)
            seen[skill.name] = skill

        self._skills = seen
        return seen

    def _scan_directory(self, path: Path) -> list[SkillDef]:
        results: list[SkillDef] = []
        if not path.is_dir():
            return results

        for entry in sorted(path.iterdir()):
            if not entry.is_file() or entry.suffix != ".md":
                continue
            try:
                skill = parse_skill_file(entry)
                skill.source_path = entry
                results.append(skill)
            except SkillParseError as e:
                log.warning("Skipping skill '%s': %s", entry.name, e)

        return results

    def get(self, name: str) -> SkillDef | None:
        skill = self._skills.get(name)
        if skill is None:
            return None
        if skill.source_path is not None and skill.source_path.is_file():
            try:
                fresh = parse_skill_file(skill.source_path)
                fresh.source_path = skill.source_path
                self._skills[name] = fresh
                return fresh
            except SkillParseError as e:
                log.warning("Hot-reload failed for skill '%s': %s", name, e)
        return skill

    def get_catalog(self) -> list[tuple[str, str]]:
        return sorted((s.name, s.description) for s in self._skills.values())
