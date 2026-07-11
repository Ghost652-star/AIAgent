"""Layer 1 — 工具结果预算（MewCode 精简版）

每轮 ReAct：
  Pass 1  单条 tool_result 超限时落盘 + 2KB 预览（零 LLM）
  Pass 2  同一批 tool_results 聚合超限时，从大到小继续落盘
  Pass 3  每轮 LLM 调用前，裁剪距当前超过 keep_turns 的旧 tool_result
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from bugdoctor.conversation.models import Message, ToolResultBlock

# ── 常量（BugDoctor 上下文窗口较小，阈值低于 MewCode 全量版）────────

SINGLE_RESULT_CHAR_LIMIT = 12_000
AGGREGATE_CHAR_LIMIT = 48_000
PREVIEW_CHARS = 2_048
OLD_RESULT_SNIP_CHARS = 2_000
SNIP_KEEP_TURNS = 5

PERSISTED_TAG = "<persisted-output>"
SNIPPED_TAG = "<snipped>"

TOOL_RESULTS_SUBDIR = Path(".bugdoctor") / "sessions" / "tool-results"


def tool_results_dir(data_root: Path, session_id: str) -> Path:
    return data_root.resolve() / TOOL_RESULTS_SUBDIR / session_id


@dataclass
class ToolBudgetState:
    """已处理过的 tool_use_id → 替换后 content（避免重复落盘）。"""

    replacements: dict[str, str] = field(default_factory=dict)


def persist_tool_result(tool_use_id: str, content: str, session_dir: Path) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    file_path = session_dir / f"{tool_use_id}.txt"
    try:
        fd = os.open(str(file_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
    except FileExistsError:
        pass
    return file_path


def make_persisted_preview(content: str, file_path: Path) -> str:
    size_kb = len(content.encode("utf-8", errors="replace")) // 1024
    preview = content[:PREVIEW_CHARS]
    return (
        f"{PERSISTED_TAG}\n"
        f"输出过大（约 {size_kb}KB），完整内容已保存到：\n"
        f"{file_path}\n\n"
        f"预览（前 {PREVIEW_CHARS // 1024}KB）：\n"
        f"{preview}\n"
        f"</persisted-output>"
    )


def budget_tool_results(
    results: list[ToolResultBlock],
    *,
    session_dir: Path,
    state: ToolBudgetState,
) -> list[ToolResultBlock]:
    """对本轮 fresh tool results 应用 Pass 1 + Pass 2，返回新列表。"""
    if not results:
        return results

    decisions: dict[str, str] = {}
    fresh: list[ToolResultBlock] = []

    for tr in results:
        if tr.tool_use_id in state.replacements:
            decisions[tr.tool_use_id] = state.replacements[tr.tool_use_id]
        elif tr.content.startswith(PERSISTED_TAG) or tr.content.startswith(SNIPPED_TAG):
            state.replacements[tr.tool_use_id] = tr.content
            decisions[tr.tool_use_id] = tr.content
        else:
            fresh.append(tr)

    persisted: set[str] = set()

    for tr in fresh:
        if len(tr.content) <= SINGLE_RESULT_CHAR_LIMIT:
            continue
        fp = persist_tool_result(tr.tool_use_id, tr.content, session_dir)
        preview = make_persisted_preview(tr.content, fp)
        decisions[tr.tool_use_id] = preview
        state.replacements[tr.tool_use_id] = preview
        persisted.add(tr.tool_use_id)

    remaining = [tr for tr in fresh if tr.tool_use_id not in persisted]
    total = sum(len(c) for c in decisions.values()) + sum(
        len(tr.content) for tr in remaining
    )

    if total > AGGREGATE_CHAR_LIMIT:
        ranked = sorted(remaining, key=lambda tr: len(tr.content), reverse=True)
        for tr in ranked:
            if total <= AGGREGATE_CHAR_LIMIT:
                break
            fp = persist_tool_result(tr.tool_use_id, tr.content, session_dir)
            preview = make_persisted_preview(tr.content, fp)
            old_len = len(tr.content)
            decisions[tr.tool_use_id] = preview
            state.replacements[tr.tool_use_id] = preview
            total -= old_len - len(preview)

    out: list[ToolResultBlock] = []
    for tr in results:
        if tr.tool_use_id in decisions:
            content = decisions[tr.tool_use_id]
        else:
            content = tr.content
            state.replacements.setdefault(tr.tool_use_id, content)
        out.append(
            ToolResultBlock(
                tool_use_id=tr.tool_use_id,
                content=content,
                is_error=tr.is_error,
            )
        )
    return out


def _count_completed_turns(history: list[Message]) -> int:
    return sum(
        1
        for m in history
        if m.role == "assistant" and not m.tool_uses
    )


def snip_stale_tool_results(
    history: list[Message],
    *,
    keep_turns: int = SNIP_KEEP_TURNS,
) -> None:
    """Pass 3：就地裁剪过早轮次的 tool_result（不调 LLM）。"""
    total_turns = _count_completed_turns(history)
    if total_turns <= keep_turns:
        return

    old_boundary = total_turns - keep_turns
    turns_seen = 0

    for i, msg in enumerate(history):
        if msg.role == "assistant" and not msg.tool_uses:
            turns_seen += 1
        if turns_seen <= old_boundary or not msg.tool_results:
            continue

        new_results: list[ToolResultBlock] = []
        changed = False
        for tr in msg.tool_results:
            if (
                tr.content.startswith(SNIPPED_TAG)
                or tr.content.startswith(PERSISTED_TAG)
                or len(tr.content) <= OLD_RESULT_SNIP_CHARS
            ):
                new_results.append(tr)
                continue
            preview = tr.content[:200]
            orig_len = len(tr.content)
            new_content = (
                f"{SNIPPED_TAG}\n"
                f"（旧工具结果已裁剪，原始约 {orig_len} 字符）\n"
                f"{preview}\n"
                f"… (snipped)"
            )
            new_results.append(
                ToolResultBlock(
                    tool_use_id=tr.tool_use_id,
                    content=new_content,
                    is_error=tr.is_error,
                )
            )
            changed = True

        if changed:
            history[i] = Message(
                role=msg.role,
                content=msg.content,
                tool_uses=list(msg.tool_uses),
                tool_results=new_results,
            )
