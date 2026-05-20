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
| Bulk code generation, boilerplate | DeepSeek V4-Flash | ~20x cheaper than Sonnet, strong code quality |
| Complex reasoning, algorithm design | DeepSeek V4-Flash (thinking ON) | Built-in CoT reasoning, cheap per token |
| Subtitle translation (per-line bulk) | DeepSeek V4-Flash | Cost-optimized for high-volume text |
| Sensitive code (auth, secrets handling) | Claude Sonnet | Trust + safety guarantees |
| Deep research + complex multi-step | DeepSeek V4-Pro | Stronger than Flash, still cheaper than Sonnet |

### DeepSeek API Integration

DeepSeek API is OpenAI-compatible — use `openai` SDK with base URL override:

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

# V4-Flash — general code + text (non-thinking mode)
response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=4096,
)

# V4-Flash — reasoning mode (thinking ON)
# DeepSeek V4 models have built-in thinking; enable via budget_tokens
response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=8000,
    extra_body={"thinking": {"type": "enabled", "budget_tokens": 4000}},
)
# thinking response exposes reasoning separately:
# response.choices[0].message.reasoning_content  ← chain-of-thought
# response.choices[0].message.content            ← final answer

# V4-Pro — stronger model for complex tasks
response = client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=4096,
)
```

**Deprecated (avoid):** `deepseek-chat` و `deepseek-reasoner` — هر دو در 2026/07/24 بازنشست می‌شوند. از `deepseek-v4-flash` استفاده کن.

### Economy Routing Logic

```python
def select_model(task_type: str, is_sensitive: bool = False) -> tuple[str, str]:
    """Returns (provider, model_id)"""
    if is_sensitive:
        return ("anthropic", "claude-sonnet-4-6")

    routing = {
        "planning":     ("anthropic",  "claude-sonnet-4-6"),
        "code_bulk":    ("deepseek",   "deepseek-v4-flash"),
        "reasoning":    ("deepseek",   "deepseek-v4-flash"),   # use thinking=enabled
        "translation":  ("deepseek",   "deepseek-v4-flash"),
        "research":     ("deepseek",   "deepseek-v4-pro"),
        "review":       ("anthropic",  "claude-sonnet-4-6"),
    }
    return routing.get(task_type, ("anthropic", "claude-sonnet-4-6"))
```

### Cost Reference (2026-05)

| Model | Context | Input cache miss | Output |
|---|---|---|---|
| Claude Opus 4.7 | 200K | ~$15/1M | ~$75/1M |
| Claude Sonnet 4.6 | 200K | ~$3/1M | ~$15/1M |
| DeepSeek V4-Pro | 1M | $0.435/1M | $0.87/1M |
| DeepSeek V4-Flash | 1M | $0.14/1M | $0.28/1M |

DeepSeek cache hit prices are ~50x cheaper (V4-Flash: $0.0028/1M input).

**Rule:** برای هر تسکی که DeepSeek V4-Flash کافیه → استفاده کن. برای تصمیم‌گیری و کد حساس → Sonnet.

### Config Pattern

```yaml
# config.yaml — economy mode
ai:
  default: anthropic/claude-sonnet-4-6
  economy:
    code_generation: deepseek/deepseek-v4-flash
    reasoning: deepseek/deepseek-v4-flash   # enable thinking mode via API
    translation: deepseek/deepseek-v4-flash
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
