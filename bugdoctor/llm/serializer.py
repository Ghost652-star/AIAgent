from __future__ import annotations

from typing import Any

from bugdoctor.conversation.models import Message


def build_chat_completion_messages(
    history: list[Message],
    system: str,
) -> list[dict[str, Any]]:
    """内部 Message → OpenAI API dict 格式"""
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})

    for msg in history:
        if msg.tool_results:
            for tr in msg.tool_results:
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr.tool_use_id,
                        "content": tr.content,
                    }
                )
            continue

        if msg.tool_uses:
            tool_calls = [
                {
                    "id": tu.tool_use_id,
                    "type": "function",
                    "function": {
                        "name": tu.tool_name,
                        "arguments": __import__("json").dumps(tu.arguments, ensure_ascii=False),
                    },
                }
                for tu in msg.tool_uses
            ]
            out.append(
                {
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": tool_calls,
                }
            )
            continue

        out.append({"role": msg.role, "content": msg.content})

    return out
