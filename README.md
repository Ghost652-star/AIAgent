# BugDoctor

假设驱动的 Bug 诊断 Agent（课程设计 C02）。采用**结构式 ReAct**（代码 while 循环 + 原生 tool calling），支持 Skill 动态加载、Bug 模式记忆、Session 持久化，以及 Context7 MCP 框架文档查询。

---

## 环境要求

| 项目 | 要求 |
|------|------|
| Python | **3.11+** |
| 操作系统 | Windows / macOS / Linux（推荐 Windows Terminal 或 UTF-8 终端） |
| LLM API | OpenAI 兼容接口（如 DeepSeek、阿里云 MaaS 等） |
| 可选 | Node.js + npx（仅在使用 Context7 MCP 时需要） |

---

## 依赖安装

### 1. 克隆仓库

```bash
git clone https://github.com/Ghost652-star/AIAgent.git
cd AIAgent
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. 安装项目依赖

```bash
pip install -e .
pip install colorama
```

`pyproject.toml` 已声明：`openai`、`pydantic`、`pyyaml`、`httpx`、`mcp`。终端颜色输出依赖 `colorama`（Windows 下建议安装）。

---

## 配置说明

配置按**多层 YAML 合并**（后者覆盖前者）：

1. `bugdoctor/config.yaml`
2. `bugdoctor/config.local.yaml`
3. `{仓库根}/.bugdoctor/config.yaml`
4. `{仓库根}/.bugdoctor/config.local.yaml`
5. `{诊断项目}/.bugdoctor/config.yaml`（可选）

也可通过环境变量设置密钥（优先级低于 YAML 中显式填写的 key）：

| 环境变量 | 说明 |
|----------|------|
| `BUGDOCTOR_API_KEY` | 主 LLM API Key |
| `BUGDOCTOR_MODEL` | 主模型名 |
| `BUGDOCTOR_BASE_URL` | API Base URL |
| `BUGDOCTOR_RECALL_API_KEY` | 记忆召回专用（可选） |
| `BUGDOCTOR_COMPACT_API_KEY` | 上下文压缩专用（可选） |

### 最小配置（LLM）

复制示例并填写 API Key：

```bash
cp bugdoctor/config.example.yaml bugdoctor/config.local.yaml
```

编辑 `bugdoctor/config.local.yaml`：

```yaml
llm:
  provider: openai-compat
  model: deepseek-v4-pro
  api_key: "你的API密钥"
  base_url: https://api.deepseek.com
  max_output_tokens: 4096
```

### 可选：MCP（Context7 框架文档）

复制应用级示例（与 memory、sessions、skills 同级）：

```bash
cp .bugdoctor/config.example.yaml .bugdoctor/config.local.yaml
```

在 `.bugdoctor/config.local.yaml` 中取消注释并填写，例如：

```yaml
mcp_servers:
  - name: context7
    command: npx
    args: ["-y", "@upstash/context7-mcp"]
    env:
      CONTEXT7_API_KEY: "你的Context7密钥"
```

> **注意：** `config.local.yaml` 含密钥，已在 `.gitignore` 中忽略，请勿提交到 Git。

### Skill 定义

5 个内置 Skill 位于 **`.bugdoctor/skills/*.md`**（已纳入版本库）。克隆后即可使用，无需额外下载。

---

## 运行方法

在仓库根目录执行：

```bash
# 诊断当前目录下的项目
python -m bugdoctor

# 指定待诊断项目路径
python -m bugdoctor --project path/to/your/project

# 强制新建 Session（跳过历史选择）
python -m bugdoctor --new

# 恢复指定 Session
python -m bugdoctor --session 20260704_123456_abcd

# 使用自定义配置文件
python -m bugdoctor --config path/to/config.yaml
```

启动后会显示：模型名、Workspace、Session ID、Skill 数量、已注册 Tools（含 MCP）。在终端粘贴错误信息，**空行发送**；输入 `quit` 或 `q` 退出。

**数据目录（运行时生成，默认不提交 Git）：**

| 路径 | 内容 |
|------|------|
| `{仓库根}/.bugdoctor/memory/` | Bug 模式长期记忆 |
| `{仓库根}/.bugdoctor/sessions/` | 对话 Session（JSONL） |
| `{诊断项目}/.bugdoctor/module-map.md` | 多模块项目的模块关系图（Agent 生成） |

---

## 典型使用示例

### 示例 1：Python Traceback 诊断

**场景：** 运行项目时出现 Python 栈追踪，需要定位根因。

**操作：**

```bash
python -m bugdoctor --project tests/python_traceback_demo
```

**输入（粘贴 Traceback 后空行发送）：**

```text
运行 main.py 报错：

Traceback (most recent call last):
  File "main.py", line 12, in <module>
    main()
  File "services/report.py", line 45, in generate
    total = amount * rate
TypeError: can't multiply sequence by non-int of type 'float'
```

**预期行为：**

1. Agent 根据 Skill 目录加载 `parse-stack-trace`（或直接使用读文件工具）
2. 按栈帧 `read_file` 相关源码，形成假设表
3. 输出中文诊断：根因 + `file:line` + 修复建议（**不主动改代码**）
4. 若本轮使用了工具，诊断结束后自动写入/更新 Bug 模式记忆

---

### 示例 2：ImportError / 环境依赖排查

**场景：** 依赖或 Python 环境有问题，不应先改业务代码。

**操作：**

```bash
python -m bugdoctor --project tests/import_error_demo
```

**输入：**

```text
ModuleNotFoundError: No module named 'pandas'
我明明 pip install 过了，还是报错。
```

**预期行为：**

1. 加载 `check-env-dependencies` Skill
2. 调用 `get_environment` 查看当前解释器与已装包
3. 必要时 `read_file` 查看 `requirements.txt` / `pyproject.toml`
4. 结论区分：包装错环境、虚拟环境未激活、包装在了系统 Python 等
5. 给出环境侧修复建议，而非直接 `edit_file`

---

### 示例 3：框架 API 问题 + MCP 查文档（LangChain 等）

**场景：** 第三方库 API 变更导致报错，需要查最新官方文档。

**前置：** 已配置 `.bugdoctor/config.local.yaml` 中的 Context7 MCP。

**操作：**

```bash
python -m bugdoctor --project tests/langchain_demo
```

**输入：**

```text
LangChain 代码报错：
ImportError: cannot import name 'ChatOpenAI' from 'langchain'

from langchain import ChatOpenAI
```

**预期行为：**

1. 先走环境/依赖排查，或加载 `lookup-framework-docs` Skill
2. 调用 `mcp_context7_resolve-library-id`、`mcp_context7_query-docs` 查询迁移说明
3. 结合本地 `read_file` 验证项目中的 import 写法
4. 给出基于文档的修复建议（如改用 `langchain-openai` 包路径）

---

### 补充：用户授权后的修复

诊断完成后，若需要 Agent 直接改代码，**必须显式授权**：

```text
请帮我修复这个 bug
```

Agent 会加载 `apply-fix` Skill：先 grep 影响面、评估风险，再 `edit_file`，并用 `run_command` 验证。

---

## 项目结构

仓库分为 **Python 包**（`bugdoctor/`）与 **运行时数据目录**（`.bugdoctor/`）两部分，职责不要混淆。

```text
AIAgent/
├── pyproject.toml                 # 项目元数据与依赖
├── README.md
├── .gitignore
│
├── bugdoctor/                     # Python 包 — Agent 实现代码
│   ├── __init__.py
│   ├── __main__.py                # CLI 入口（python -m bugdoctor）
│   ├── app.py                     # 终端主循环、Session/记忆持久化
│   ├── config.py                  # 多级 YAML 配置合并
│   ├── config.example.yaml        # LLM 配置示例
│   ├── project_map.py             # 模块图 reminder（配合 map-project-modules）
│   │
│   ├── agent/
│   │   └── loop.py                # 结构式 ReAct 循环（Think→Act→Observe）
│   │
│   ├── conversation/
│   │   ├── models.py              # Message / ToolUseBlock / ToolResultBlock
│   │   └── manager.py             # 对话历史与 system-reminder 注入
│   │
│   ├── llm/
│   │   ├── client.py              # OpenAI 兼容流式 API 客户端
│   │   ├── events.py              # StreamEvent 事件类型
│   │   └── serializer.py          # Message → OpenAI 请求格式
│   │
│   ├── tools/
│   │   ├── base.py                # Tool 抽象、ToolRegistry
│   │   ├── factory.py             # 注册全部内置工具
│   │   ├── sandbox.py             # 路径沙箱
│   │   ├── read_tracker.py        # edit 前必须先 read
│   │   ├── read_file.py
│   │   ├── glob_files.py
│   │   ├── grep_code.py
│   │   ├── run_command.py
│   │   ├── get_environment.py
│   │   ├── write_file.py          # 仅允许写入 .bugdoctor/
│   │   ├── edit_file.py
│   │   └── load_skill.py          # 激活 Skill、触发工具过滤
│   │
│   ├── skills/                    # Skill 机制（代码，不是 Skill 正文）
│   │   ├── parser.py              # 解析 .md frontmatter
│   │   ├── loader.py              # 扫描 .bugdoctor/skills/
│   │   ├── manager.py             # 激活、SOP 注入、allowedTools
│   │   └── paths.py               # Skill 目录路径约定
│   │
│   ├── memory/
│   │   ├── store.py               # Bug 模式记忆写入（LLM 维护决策）
│   │   ├── recall.py              # 记忆召回（LLM 选择 ≤3 条）
│   │   ├── session.py             # Session JSONL 持久化
│   │   └── replay.py              # 恢复 Session 时的终端回放
│   │
│   ├── mcp/
│   │   ├── client.py              # MCP stdio / HTTP 连接
│   │   ├── manager.py             # 加载 MCP 配置、注册工具
│   │   └── tool_wrapper.py        # MCP 工具 → BugDoctor Tool
│   │
│   ├── context/
│   │   └── compact.py             # 上下文超阈值时 LLM 摘要压缩
│   │
│   └── prompts/
│       ├── builder.py             # 按 priority 拼接 PromptSection
│       ├── sections.py            # 身份、ReAct 规则、输出风格
│       └── system.py              # build_system_prompt()
│
└── .bugdoctor/                    # 运行时数据（仓库内仅提交部分文件）
    ├── skills/                    # ✅ 已提交 — 5 个 Skill SOP 正文
    │   ├── parse-stack-trace.md
    │   ├── map-project-modules.md
    │   ├── check-env-dependencies.md
    │   ├── lookup-framework-docs.md
    │   └── apply-fix.md
    ├── config.example.yaml        # ✅ 已提交 — MCP 配置示例
    ├── config.local.yaml          # ❌ 不提交 — 含 API Key
    ├── memory/                    # ❌ 不提交 — Bug 模式长期记忆
    └── sessions/                  # ❌ 不提交 — 对话 JSONL
```

**诊断工作区**（`--project` 指向的项目）下还可能生成：

```text
{your_project}/.bugdoctor/
└── module-map.md                  # map-project-modules Skill 写入的模块关系图
```

### 分层职责

| 层级 | 目录 | 职责 |
|------|------|------|
| Layer 1 | `llm/` | 只负责与 LLM API 通信，不知工具与 ReAct |
| Layer 2 | `conversation/` | 维护 Message 历史，不知工具如何执行 |
| Layer 3 | `agent/` | ReAct 循环，调度 LLM 与工具 |
| Layer 4 | `tools/` `skills/` `memory/` `mcp/` | 工具、Skill、记忆、MCP 能力 |
| Layer 5 | `app.py` | 终端 I/O，装配以上全部模块 |

### 两个「skills」目录的区别

| 路径 | 类型 | 说明 |
|------|------|------|
| `bugdoctor/skills/` | Python 代码 | 解析、加载、激活 Skill 的机制 |
| `.bugdoctor/skills/` | Markdown 文档 | Agent 实际执行的 SOP 与 allowedTools 定义 |

---

## 常见问题

**Q：启动报 API key missing？**  
A：检查 `bugdoctor/config.local.yaml` 或环境变量 `BUGDOCTOR_API_KEY`。

**Q：MCP 工具未出现在 Tools 列表？**  
A：确认 `.bugdoctor/config.local.yaml` 中 `mcp_servers` 已配置，且本机可运行 `npx`（stdio 模式）。

**Q：Skill 没有加载？**  
A：Skill 由 LLM 根据 catalog 中的 description 自主调用 `load_skill`；复杂报错可手动在对话中提示「请先 load_skill(parse-stack-trace)」。

**Q：记忆 / Session 会提交到 Git 吗？**  
A：不会。`.gitignore` 已忽略 `.bugdoctor/memory/`、`.bugdoctor/sessions/` 及含密钥的 `config.local.yaml`。
