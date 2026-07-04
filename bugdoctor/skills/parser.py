from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

VALID_NAME_RE = re.compile(r"^[a-z][a-z0-9\-]*$")
VALID_MODES = {"inline"}


class SkillParseError(Exception):
    pass


@dataclass
class SkillDef:
    name: str
    description: str
    prompt_body: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    mode: Literal["inline"] = "inline"
    source_path: Path | None = None


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    stripped = raw.lstrip()
    if not stripped.startswith("---"):
        raise SkillParseError("Missing YAML frontmatter (must start with ---)")

    end = stripped.find("---", 3)
    if end == -1:
        raise SkillParseError("Unclosed YAML frontmatter (missing closing ---)")

    yaml_block = stripped[3:end]
    body = stripped[end + 3 :].lstrip("\n")

    try:
        meta = yaml.safe_load(yaml_block)
    except yaml.YAMLError as e:
        raise SkillParseError(f"Invalid YAML in frontmatter: {e}") from e

    if not isinstance(meta, dict):
        raise SkillParseError("Frontmatter must be a YAML mapping")

    return meta, body


def _validate_meta(meta: dict, source: str = "") -> None:
    ctx = f" in {source}" if source else ""

    if "name" not in meta:
        raise SkillParseError(f"Missing required field 'name'{ctx}")
    if "description" not in meta:
        raise SkillParseError(f"Missing required field 'description'{ctx}")

    name = meta["name"]
    if not isinstance(name, str) or not VALID_NAME_RE.match(name):
        raise SkillParseError(
            f"Invalid skill name '{name}'{ctx}: "
            "must be lowercase letters, digits, and hyphens"
        )

    mode = meta.get("mode", "inline")
    if mode not in VALID_MODES:
        raise SkillParseError(f"Invalid mode '{mode}'{ctx}: only 'inline' supported")


def parse_skill_file(path: Path) -> SkillDef:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SkillParseError(f"Cannot read skill file {path}: {e}") from e

    meta, body = parse_frontmatter(raw)
    _validate_meta(meta, str(path))

    allowed = meta.get("allowedTools", [])
    if allowed is not None and not isinstance(allowed, list):
        raise SkillParseError(f"allowedTools must be a list{path}")

    return SkillDef(
        name=meta["name"],
        description=meta["description"],
        prompt_body=body,
        allowed_tools=list(allowed or []),
        mode="inline",
        source_path=path,
    )
