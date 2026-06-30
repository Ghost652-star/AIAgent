from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class LLMConfig:
    provider: str = "openai-compat"
    model: str = "deepseek-v4-pro"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    max_output_tokens: int = 4096


@dataclass
class AppConfig:
    llm: LLMConfig
    project_root: Path
    max_agent_iterations: int = 30


def _default_config_paths(project_root: Path) -> list[Path]:
    pkg_root = Path(__file__).resolve().parent
    return [
        pkg_root / "config.yaml",
        pkg_root / "config.local.yaml",
        project_root / ".bugdoctor" / "config.yaml",
        project_root / ".bugdoctor" / "config.local.yaml",
    ]


def load_config(project_root: Path, config_path: Path | None = None) -> AppConfig:
    data: dict = {}
    chosen: Path | None = None

    if config_path and config_path.exists():
        chosen = config_path
    else:
        for candidate in _default_config_paths(project_root):
            if candidate.exists():
                chosen = candidate
                break

    if chosen:
        data = yaml.safe_load(chosen.read_text(encoding="utf-8")) or {}

    llm_data = data.get("llm", {})
    llm = LLMConfig(
        provider=llm_data.get("provider", "openai-compat"),
        model=llm_data.get("model", os.getenv("BUGDOCTOR_MODEL", "deepseek-v4-pro")),
        api_key=llm_data.get("api_key", os.getenv("BUGDOCTOR_API_KEY", "")),
        base_url=llm_data.get("base_url", os.getenv("BUGDOCTOR_BASE_URL", "https://api.deepseek.com")),
        max_output_tokens=int(llm_data.get("max_output_tokens", 4096)),
    )
    return AppConfig(
        llm=llm,
        project_root=project_root.resolve(),
        max_agent_iterations=int(data.get("max_agent_iterations", 30)),
    )
