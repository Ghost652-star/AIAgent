from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from bugdoctor.mcp.client import MCPServerConfig


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
    recall_llm: LLMConfig | None = None
    compact_llm: LLMConfig | None = None
    compact_threshold: int = 8000
    mcp_servers: list[MCPServerConfig] = field(default_factory=list)

    def recall_client_config(self) -> LLMConfig:
        """记忆检索专用 LLM；未配置时回退到主 llm。"""
        return self.recall_llm or self.llm

    def compact_client_config(self) -> LLMConfig | None:
        """摘要压缩专用 LLM；未配置时回退到主 llm。"""
        if self.compact_llm is not None:
            return self.compact_llm
        if self.recall_llm is not None:
            return self.recall_llm
        return None


def app_data_root() -> Path:
    """BugDoctor 自身项目根（`bugdoctor/` 的上一级；会话/记忆写在此下的 `.bugdoctor/`）。"""
    return Path(__file__).resolve().parent.parent


def _default_config_paths(project_root: Path) -> list[Path]:
    """配置合并顺序（后者覆盖前者）：
    包内默认 → BugDoctor 应用根 .bugdoctor/（memory/skills/mcp）→ 诊断工作区 .bugdoctor/
    """
    pkg_root = Path(__file__).resolve().parent
    data_root = app_data_root()
    return [
        pkg_root / "config.yaml",
        pkg_root / "config.local.yaml",
        data_root / ".bugdoctor" / "config.yaml",
        data_root / ".bugdoctor" / "config.local.yaml",
        project_root / ".bugdoctor" / "config.yaml",
        project_root / ".bugdoctor" / "config.local.yaml",
    ]


def _parse_mcp_servers(raw: list | None) -> list[MCPServerConfig]:
    if not raw:
        return []
    if not isinstance(raw, list):
        return []

    servers: list[MCPServerConfig] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name:
            continue
        command = entry.get("command")
        url = entry.get("url")
        servers.append(
            MCPServerConfig(
                name=str(name),
                command=str(command) if command else None,
                args=[str(a) for a in entry.get("args", [])],
                url=str(url) if url else None,
                headers={str(k): str(v) for k, v in (entry.get("headers") or {}).items()},
                env={str(k): str(v) for k, v in (entry.get("env") or {}).items()},
            )
        )
    return servers


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _parse_llm_config(data: dict, *, env_prefix: str = "BUGDOCTOR") -> LLMConfig:
    return LLMConfig(
        provider=data.get("provider", "openai-compat"),
        model=data.get("model", os.getenv(f"{env_prefix}_MODEL", "deepseek-v4-pro")),
        api_key=data.get("api_key", os.getenv(f"{env_prefix}_API_KEY", "")),
        base_url=data.get(
            "base_url",
            os.getenv(f"{env_prefix}_BASE_URL", "https://api.deepseek.com"),
        ),
        max_output_tokens=int(data.get("max_output_tokens", 4096)),
    )


def load_config(project_root: Path, config_path: Path | None = None) -> AppConfig:
    data: dict = {}

    if config_path and config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    else:
        for candidate in _default_config_paths(project_root):
            if candidate.exists():
                layer = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
                data = _deep_merge(data, layer)

    llm = _parse_llm_config(data.get("llm", {}))

    recall_llm: LLMConfig | None = None
    if "recall_llm" in data:
        recall_llm = _parse_llm_config(
            data.get("recall_llm", {}),
            env_prefix="BUGDOCTOR_RECALL",
        )

    compact_llm: LLMConfig | None = None
    if "compact_llm" in data:
        compact_llm = _parse_llm_config(
            data.get("compact_llm", {}),
            env_prefix="BUGDOCTOR_COMPACT",
        )

    return AppConfig(
        llm=llm,
        project_root=project_root.resolve(),
        max_agent_iterations=int(data.get("max_agent_iterations", 30)),
        recall_llm=recall_llm,
        compact_llm=compact_llm,
        compact_threshold=int(data.get("compact_threshold", 8000)),
        mcp_servers=_parse_mcp_servers(data.get("mcp_servers")),
    )
