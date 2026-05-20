---
description: Protocol for AI model selection, multi-agent task decomposition, and prompt engineering within Claude Code.
updated: 2026-05-20
---

# AI Optimization Workflow (Claude Code)

## 1. Model Selection Strategy

Claude Code provides three models. Select based on task complexity and cost:

| Model | ID | Use When |
|---|---|---|
| **Opus** | `claude-opus-4-7` | Architecture decisions, complex debugging, code review, planning |
| **Sonnet** | `claude-sonnet-4-6` | Default for most tasks — implementation, refactoring, analysis |
| **Haiku** | `claude-haiku-4-5-20251001` | Bulk operations, simple lookups, fast iteration |

**Rule:** Default to Sonnet. Only escalate to Opus when the task requires deep reasoning across many files or when a Sonnet attempt fails.

## 1.5 Economy Mode: Sonnet + DeepSeek

برای کدنویسی اقتصادی‌تر وقتی Opus لازم نیست، از ترکیب **Claude Sonnet + DeepSeek** استفاده کن.

### Model Selection Matrix (Economy)

| Task | Model | Why |
|---|---|---|
| Planning, architecture, critical bug | Claude Sonnet | Anthropic quality for decision-making |
| Bulk code generation, boilerplate | DeepSeek V3 | ~10x cheaper than Sonnet, similar code quality |
| Complex reasoning, algorithm design | DeepSeek R1 | Strong reasoning, cheap per token |
| Subtitle translation (per-line bulk) | DeepSeek V3 | Cost-optimized for high-volume text |
| Sensitive code (auth, secrets handling) | Claude Sonnet | Trust + safety guarantees |

### DeepSeek API Integration

DeepSeek API is OpenAI-compatible — use `openai` SDK with base URL override:

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

# V3 — general code + text
response = client.chat.completions.create(
    model="deepseek-chat",      # = DeepSeek V3
    messages=[{"role": "user", "content": prompt}],
    max_tokens=2048,
)

# R1 — reasoning tasks
response = client.chat.completions.create(
    model="deepseek-reasoner",  # = DeepSeek R1
    messages=[{"role": "user", "content": prompt}],
)
# R1 exposes reasoning_content separately:
# response.choices[0].message.reasoning_content  ← chain-of-thought
# response.choices[0].message.content            ← final answer
```

### Economy Routing Logic

```python
def select_model(task_type: str, is_sensitive: bool = False) -> tuple[str, str]:
    """Returns (provider, model_id)"""
    if is_sensitive:
        return ("anthropic", "claude-sonnet-4-6")

    routing = {
        "planning":     ("anthropic", "claude-sonnet-4-6"),
        "code_bulk":    ("deepseek",  "deepseek-chat"),
        "reasoning":    ("deepseek",  "deepseek-reasoner"),
        "translation":  ("deepseek",  "deepseek-chat"),
        "review":       ("anthropic", "claude-sonnet-4-6"),
    }
    return routing.get(task_type, ("anthropic", "claude-sonnet-4-6"))
```

### Cost Reference (approx. 2026)

| Model | Input ($/1M tokens) | Output ($/1M tokens) |
|---|---|---|
| Claude Opus 4.7 | ~$15 | ~$75 |
| Claude Sonnet 4.6 | ~$3 | ~$15 |
| DeepSeek V3 | ~$0.27 | ~$1.10 |
| DeepSeek R1 | ~$0.55 | ~$2.19 |

**Rule:** برای هر تسکی که DeepSeek V3 کافیه → استفاده کن. برای تصمیم‌گیری و کد حساس → Sonnet.

### Config Pattern

```yaml
# config.yaml — economy mode
ai:
  default: anthropic/claude-sonnet-4-6
  economy:
    code_generation: deepseek/deepseek-chat
    reasoning: deepseek/deepseek-reasoner
    translation: deepseek/deepseek-chat
  sensitive_tasks:
    - auth
    - secrets
    - payment
```

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
```

## 2. Multi-Agent Task Decomposition

For complex tasks, decompose into parallel subagents rather than a single long conversation.

### Available Subagent Types

| Type | When to Use |
|---|---|
| `Plan` | Design implementation strategy before writing code. Use `/plan` or spawn Plan agent. |
| `Explore` | Read-only codebase search. Protect main context from large grep/read operations. |
| `general-purpose` | Multi-step tasks, research + implementation, anything spanning multiple tools. |
| `claude-code-guide` | Questions about Claude Code API, SDK, CLI features, hooks, MCP. |

### Decomposition Rules

1. **Plan before code:** For any task touching >3 files, enter Plan Mode first.
2. **Parallel reads:** Spawn Explore agents for independent search tasks (e.g., "where is X defined" + "find all callers of Y" → two parallel Explore agents).
3. **Context protection:** If a subtask will generate >500 lines of output (logs, test results, large file reads), run it via a subagent so it doesn't pollute the main context.
4. **Sequential dependency:** If step B needs step A's output, run them sequentially. Never pass placeholder values.

### Task Prompt Format (for subagents)

When creating task prompts for subagents, always include:
```
Goal: [what needs to be done]
Context: [relevant files, recent changes, constraints]
Output: [expected format and length of response]
Do NOT: [common mistakes to avoid]
```

## 3. Prompt Engineering Standards

**Rule:** Prompts are code. Store reusable prompts in `lib/python/subtitle/prompts/` (Python) or document them in the relevant `.agent/skills/*.md`.

### Prompt Structure (for AI-calling code)
```
Role: [specific role]
Task: [concrete, measurable action]
Constraints: [hard limits — format, length, language]
Output Format: [exact structure of the expected response]
```

### Anti-Patterns (Forbidden)
- Vague instructions: "translate this well" → use "translate to informal Tehran Persian, output JSON only"
- Nested instructions: keep prompts flat and single-purpose
- Buried prompts inside Python f-strings → load from `.txt` file via `Path(prompts_dir / "task.txt").read_text()`

## 4. Context Management

Claude Code context degrades with length. Apply these rules:

1. **CLAUDE.md is the anchor.** Keep it updated so any new session can start cold without losing project context.
2. **Subagents for exploration.** Never grep 70 files in the main context — spawn Explore.
3. **Compact summaries.** After a long debug session, summarize the root cause in CLAUDE.md before closing.
4. **Memory system.** Use `/Users/su6i/.claude/projects/*/memory/` for facts that must survive across sessions (user preferences, architectural decisions, feedback).

## 5. Whisper / LLM Integration (amir-cli specific)

For subtitle translation and transcription tasks in this project:

- **Transcription:** faster-whisper (CPU) or mlx-whisper (Apple Silicon). See `.agent/skills/mlx-whisper.md`.
- **Translation:** Anthropic Claude API via `lib/python/subtitle/workflow/translation_stage.py`.
- **Prompt storage:** Translation prompts live in `lib/python/subtitle/processor.py → get_translation_prompt()`.
- **Model for translation:** Default `claude-haiku-4-5-20251001` (cost-optimized for per-line bulk translation). Escalate to Sonnet only for low-confidence lines.

## 6. API Quota & Error Handling

```python
# Standard retry pattern for Anthropic API calls
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    retry=retry_if_exception_type(anthropic.RateLimitError),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5)
)
def call_claude(client, messages, model="claude-haiku-4-5-20251001"):
    return client.messages.create(model=model, max_tokens=1024, messages=messages)
```

**On persistent 429:** Log to `~/.amir_cli/api_state.json` and surface to user with retry-after time. Do NOT silently skip lines.
