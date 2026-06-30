# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

BugDoctor — Hypothesis-driven bug diagnosis agent, built as the D01 数据探索 Agent course project. The system follows a **structural ReAct** paradigm (code-driven while loop with native tool calling), NOT prompt-level ReAct (regex parsing of LLM text output).

Reference implementation: `F:\python_project\NowCode\mewcode\` — the memory, error-handling, skill, and MCP patterns there inform this project's design.

## Commands

```bash
# Run the agent (interactive terminal mode)
python -m bugdoctor

# Or with explicit config
python -m bugdoctor --config path/to/config.yaml
```

No test suite yet. Dependencies: `openai`, `pydantic`, `pyyaml`, `httpx`.

## Architecture — Layered Design

Layers are numbered by dependency: lower layers know nothing about upper layers.

| Layer | Module | Responsibility |
|-------|--------|----------------|
| 1 | `llm/` | Talks to the model API. Knows NOTHING about tools, ReAct, or memory. |
| 2 | `conversation/` | Owns turn history (`Message` list). Knows about tool blocks but NOT about how tools execute. |
| 3 | (future) `tools/` | Tool registry + execution. Depends on Layer 2 for `ToolUseBlock`/`ToolResultBlock`. |
| 4 | (future) `agent/` | The ReAct loop. Depends on Layers 1-3. |
| 5 | `chat/` + `app.py` | Terminal I/O. Wires everything together. |

### Layer 1 — `llm/`

- **`events.py`**: `StreamEvent` union type — `TextDelta | ToolCallStart | ToolCallDelta | ToolCallComplete | StreamEnd`. This is the ONLY data the LLM client emits.
- **`client.py`**: `OpenAICompatClient` streams from the API and yields `StreamEvent`s. One client instance is shared — memory/skill side-calls reuse it.
- **`serializer.py`**: Converts the vendor-neutral internal `Message` list → OpenAI chat-completion format. Only file that knows OpenAI's wire format.

### Layer 2 — `conversation/`

- **`models.py`**: `Message` is a vendor-neutral turn record with `tool_uses: list[ToolUseBlock]` and `tool_results: list[ToolResultBlock]`. Token estimation uses a simple `chars/3.5` heuristic.
- **`manager.py`**: `ConversationManager` maintains `history: list[Message]` plus a token baseline anchor for efficient incremental counting.

### Current State — "Step 1"

The `ChatSession` comment says "Step 1: multi-turn dialogue only — no tools, skills, or memory." The layered architecture is in place, but Layers 3 (tools) and 4 (agent ReAct loop) are not yet built. The current `chat/session.py` sends the full history to the LLM without tools.

### Design Decisions to Understand

- **Why vendor-neutral `Message`?** So the ReAct loop, memory system, and serializer all operate on the same data structure without coupling to any specific LLM provider's format. Switching providers means changing only `serializer.py`.
- **Why `StreamEvent` union?** The ReAct loop consumes a single async stream and pattern-matches on event types — no callback spaghetti.
- **Token estimation (not counting)**: `chars/3.5` is fast and good enough for compaction decisions. Exact token counts require an extra API call.
- **Config cascading**: `config.local.yaml` > `config.yaml` > env vars. Secrets go in `config.local.yaml` (gitignored).

## Course Constraints (from memory)

When making design decisions, reference `[[course-anti-patterns]]`:
1. Each feature must demonstrate LLM **autonomous reasoning**, not just execute a preset flow.
2. Memory must be **structured extraction + recall**, not raw context stuffing.
3. Every design decision must be explainable in the student's own words.
4. Depth over breadth — a ★ topic done deeply beats a ★★★ topic done shallowly.
