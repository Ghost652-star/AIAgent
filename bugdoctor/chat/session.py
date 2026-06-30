from __future__ import annotations

from collections.abc import AsyncIterator

from bugdoctor.conversation.manager import ConversationManager
from bugdoctor.llm.client import LLMClient
from bugdoctor.llm.events import TextDelta


DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


class ChatSession:
    """单轮对话流程：记录用户输入 → 调 LLM → 流式输出 → 记录回复"""

    def __init__(
        self,
        client: LLMClient,
        conversation: ConversationManager,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self.client = client
        self.conversation = conversation
        self.system_prompt = system_prompt

    async def send(self, user_input: str) -> AsyncIterator[str]:
        self.conversation.add_user(user_input)

        assistant_text = ""
        async for event in self.client.stream(
            self.conversation,
            system=self.system_prompt,
            tools=None,
        ):
            if isinstance(event, TextDelta):
                assistant_text += event.text
                yield event.text

        self.conversation.add_assistant(assistant_text)
