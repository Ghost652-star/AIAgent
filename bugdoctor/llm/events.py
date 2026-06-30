"""LLM 流式响应的标准化事件类型"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TextDelta:
    """文字片段"""
    text: str


@dataclass
class ToolCallStart:
    """工具调用开始"""
    tool_call_id: str
    tool_name: str


@dataclass
class ToolCallDelta:
    """工具参数片段"""
    tool_call_id: str
    arguments_delta: str


@dataclass
class ToolCallComplete:
    """工具调用参数收齐"""
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class StreamEnd:
    """流结束"""
    pass


StreamEvent = TextDelta | ToolCallStart | ToolCallDelta | ToolCallComplete | StreamEnd
