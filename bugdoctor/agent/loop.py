"""ReAct Agent 循环 —— 假设驱动的 Bug 诊断
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from bugdoctor.conversation.manager import ConversationManager
from bugdoctor.conversation.models import ToolResultBlock, ToolUseBlock
from bugdoctor.context.compact import CompactEvent as CompactResult, auto_compact
from bugdoctor.context.tool_budget import (
    ToolBudgetState,
    budget_tool_results,
    snip_stale_tool_results,
    tool_results_dir,
)
from bugdoctor.llm.client import LLMClient
from bugdoctor.llm.events import TextDelta, ToolCallComplete
from bugdoctor.tools.base import ToolRegistry

if TYPE_CHECKING:
    from bugdoctor.skills.manager import SkillManager



@dataclass
class StreamText:
    """LLM 输出的文字片段，对应 ReAct 的 Thought"""
    text: str


@dataclass
class ToolUseEvent:
    """LLM 决定调用工具，对应 ReAct 的 Action"""
    tool_name: str
    arguments: dict


@dataclass
class ToolResultEvent:
    """工具执行结果，对应 ReAct 的 Observation"""
    tool_name: str
    content: str
    is_error: bool


@dataclass
class TurnComplete:
    """本轮结束"""
    pass


@dataclass
class ErrorEvent:
    """Agent 级错误"""
    message: str


@dataclass
class CompactNotification:
    """Auto-compact 触发通知"""
    before_tokens: int
    after_tokens: int
    summary: str = ""
    keep_count: int = 0


AgentEvent = StreamText | ToolUseEvent | ToolResultEvent | TurnComplete | ErrorEvent | CompactNotification


class Agent:
    

    def __init__(
        self,
        client: LLMClient,
        registry: ToolRegistry,
        conversation: ConversationManager,
        system_prompt: str,
        max_iterations: int = 30,
        compact_client: LLMClient | None = None,
        compact_threshold: int = 0,
        skill_manager: SkillManager | None = None,
        *,
        session_id: str | None = None,
        data_root: Path | None = None,
    ) -> None:
        self.client = client
        self.registry = registry
        self.conversation = conversation
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.compact_client = compact_client
        self.compact_threshold = compact_threshold
        self.skill_manager = skill_manager
        self._tool_budget_state = ToolBudgetState()
        self._tool_results_dir: Path | None = None
        if session_id and data_root is not None:
            self._tool_results_dir = tool_results_dir(data_root, session_id)

    def _tool_schemas(self) -> list[dict]:
        names = self.registry.list_names()
        allowed = (
            self.skill_manager.allowed_tool_names(names)
            if self.skill_manager
            else None
        )
        return self.registry.get_schemas(allowed=allowed)

    def _system_prompt_for_llm(self) -> str:
        """基础 system prompt + 当前已激活 Skill SOP（每轮 LLM 调用前刷新）。"""
        base = self.system_prompt
        if not self.skill_manager:
            return base
        active = self.skill_manager.build_active_skills_section()
        if not active:
            return base
        return f"{base.rstrip()}\n\n{active}"

    def _tool_allowed(self, tool_name: str) -> bool:
        if self.skill_manager is None:
            return True
        allowed = self.skill_manager.allowed_tool_names(self.registry.list_names())
        if allowed is None:
            return True
        return tool_name in allowed

    async def run(
        self,
        user_input: str,
        *,
        memory_reminder: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """执行 ReAct 循环"""
        self.conversation.add_user(user_input)
        if memory_reminder:
            self.conversation.add_system_reminder(memory_reminder)

        for _ in range(self.max_iterations):  # 代码只控制轮数上限，每轮做什么由 LLM 决定
            # ── 0a. Layer 1：裁剪旧 tool_result（零 LLM）──
            if self._tool_results_dir is not None:
                snip_stale_tool_results(self.conversation.history)

            # ── 0b. Layer 2：超阈值时 LLM 摘要压缩 ──
            if self.compact_client and self.compact_threshold > 0:
                result = await auto_compact(
                    self.conversation,
                    self.compact_client,
                    self.compact_threshold,
                )
                if result is not None:
                    yield CompactNotification(
                        before_tokens=result.before_tokens,
                        after_tokens=result.after_tokens,
                        summary=result.summary,
                        keep_count=result.keep_count,
                    )

            # ── 1. 调 LLM（带工具列表） ──
            assistant_text = ""
            tool_calls: list[ToolCallComplete] = []

            async for event in self.client.stream(
                self.conversation,
                system=self._system_prompt_for_llm(),
                tools=self._tool_schemas(),
            ):
                if isinstance(event, TextDelta):
                    assistant_text += event.text
                    yield StreamText(event.text)
                elif isinstance(event, ToolCallComplete):
                    tool_calls.append(event)

            # ── 2. 无工具调用 → LLM 判断任务完成 → 结束 ──
            if not tool_calls:
                self.conversation.add_assistant(content=assistant_text)
                yield TurnComplete()
                return

            # ── 3. 有工具调用 → 记录 LLM 的 Action ──
            uses = [
                ToolUseBlock(
                    tool_use_id=tc.tool_call_id or str(uuid.uuid4()),
                    tool_name=tc.tool_name,
                    arguments=tc.arguments,
                )
                for tc in tool_calls
            ]
            self.conversation.add_assistant(content=assistant_text, tool_uses=uses)

            # ── 4. 逐个执行工具 → 收集 Observation ──
            results = []
            for use in uses:
                yield ToolUseEvent(use.tool_name, use.arguments)
                if not self._tool_allowed(use.tool_name):
                    block = ToolResultBlock(
                        tool_use_id=use.tool_use_id,
                        content=(
                            f"Error: tool {use.tool_name!r} is not allowed under the "
                            "currently active Skill. Use load_skill to switch or pick an allowed tool."
                        ),
                        is_error=True,
                    )
                else:
                    block = await self.registry.run(
                        use.tool_name, use.arguments, use.tool_use_id
                    )
                results.append(block)
                yield ToolResultEvent(use.tool_name, block.content, block.is_error)

            # ── 4b. Layer 1：超大结果落盘 + 预览 ──
            if self._tool_results_dir is not None:
                results = budget_tool_results(
                    results,
                    session_dir=self._tool_results_dir,
                    state=self._tool_budget_state,
                )

            # ── 5. Observation 写回对话 → 回到步骤 1，LLM 据此决定下一步 ──
            self.conversation.add_tool_results(results)

        yield ErrorEvent(f"Agent reached maximum iterations ({self.max_iterations})")
