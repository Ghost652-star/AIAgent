"""Test harness: run Agent against a sample project with given input."""
import asyncio
import sys
from pathlib import Path

# Fix Windows GBK terminal for emoji output
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bugdoctor.agent.loop import Agent, StreamText, ToolUseEvent, ToolResultEvent, TurnComplete, ErrorEvent
from bugdoctor.config import load_config
from bugdoctor.conversation.manager import ConversationManager
from bugdoctor.llm.client import create_client
from bugdoctor.prompts.system import build_system_prompt
from bugdoctor.tools.factory import create_registry


async def run_test(project_path: str, bug_description: str) -> None:
    project = Path(project_path).resolve()
    config = load_config(project)
    client = create_client(config.llm)
    registry = create_registry(config.project_root)
    conversation = ConversationManager()
    system_prompt = build_system_prompt(str(config.project_root))
    agent = Agent(
        client=client,
        registry=registry,
        conversation=conversation,
        system_prompt=system_prompt,
        max_iterations=config.max_agent_iterations,
    )

    print(f"{'='*60}")
    print(f"Project: {project.name}")
    print(f"Tools: {', '.join(registry.list_names())}")
    print(f"Input: {bug_description[:100]}...")
    print(f"{'='*60}")

    async for event in agent.run(bug_description):
        if isinstance(event, StreamText):
            print(event.text, end="", flush=True)
        elif isinstance(event, ToolUseEvent):
            print(f"\n  [TOOL] {event.tool_name}({event.arguments})")
        elif isinstance(event, ToolResultEvent):
            tag = "ERR" if event.is_error else "OK"
            preview = event.content[:300].replace('\n', '\n  ')
            print(f"  [{tag}] {preview}")
        elif isinstance(event, TurnComplete):
            print("\n--- turn complete ---")
        elif isinstance(event, ErrorEvent):
            print(f"\n  [AGENT ERROR] {event.message}")

    print(f"\n{'='*60}\n")


def main():
    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    tests = [
        # (project_dir, bug_description)
        ("demo_logic_bug", (
            "I ordered 10 items at $100 each. The documentation says 10+ items "
            "get 10% discount, so total should be $900.00. But the program "
            "printed $1000.00 — no discount was applied. Please find and fix the bug."
        )),
        ("demo_state_leak", (
            "The program processes two batches. Batch 1 processes [1,2,3] and "
            "correctly says 'total historial count: 3'. Batch 2 processes [4,5] — "
            "it should say 'total historial count: 2' but instead says 5. "
            "Looks like state is leaking between batches. Find and fix the bug."
        )),
    ]

    for name, bug_text in tests:
        project = samples_dir / name
        if not project.is_dir():
            print(f"SKIP: {project} not found")
            continue
        asyncio.run(run_test(str(project), bug_text))


if __name__ == "__main__":
    main()
