from __future__ import annotations

from pathlib import Path

from bugdoctor.chat.session import ChatSession, DEFAULT_SYSTEM_PROMPT
from bugdoctor.config import load_config
from bugdoctor.conversation.manager import ConversationManager
from bugdoctor.llm.client import LLMError, create_client


async def run_app(config_path: Path | None = None) -> None:
    """终端交互入口：组装组件 → 等待输入 → 逐字输出"""
    config = load_config(Path("."), config_path)

    try:
        client = create_client(config.llm)
    except LLMError as exc:
        print(f"配置错误: {exc}")
        print("请在 bugdoctor/config.yaml 中设置 llm.api_key，或设置环境变量 BUGDOCTOR_API_KEY")
        return

    # 组装：对话历史 + 聊天流程
    conversation = ConversationManager()
    chat = ChatSession(
        client=client,
        conversation=conversation,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
    )

    print(f"BugDoctor — model: {config.llm.model}")
    print("多轮对话已就绪。输入 quit 退出。\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Bye.")
            break

        print("assistant> ", end="", flush=True)
        async for chunk in chat.send(user_input):
            print(chunk, end="", flush=True)
        print("\n")
