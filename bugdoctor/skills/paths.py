from __future__ import annotations

from pathlib import Path

AGENT_DATA_SUBDIR = Path(".bugdoctor")
SKILLS_SUBDIR = AGENT_DATA_SUBDIR / "skills"


def agent_skills_dir(agent_data_root: Path) -> Path:
    """Skill 文档目录 — 与 memory、sessions 同级：{agent_data_root}/.bugdoctor/skills/"""
    return agent_data_root.resolve() / SKILLS_SUBDIR
