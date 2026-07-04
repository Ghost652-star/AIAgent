"""项目模块图 — 路径约定与可选 reminder 注入"""

from __future__ import annotations

from pathlib import Path

MODULE_MAP_REL = Path(".bugdoctor") / "module-map.md"


def module_map_path(project_root: Path) -> Path:
    return project_root.resolve() / MODULE_MAP_REL


def module_map_reminder(project_root: Path) -> str | None:
    """若项目下已有 module-map.md，返回注入 LLM 的 reminder 文本；否则 None。"""
    if not module_map_path(project_root).is_file():
        return None
    rel = MODULE_MAP_REL.as_posix()
    return f"""\
## 项目模块图

本项目已有模块关系图：`{rel}`。
开始诊断前请先 read_file 读取该文件，在模块关系上定位本次报错链路；
不要重复 glob 全库。若模块图与当前代码明显不符，可 load_skill(map-project-modules) 刷新。"""
