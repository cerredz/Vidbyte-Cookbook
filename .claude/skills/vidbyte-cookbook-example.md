# Vidbyte Cookbook Example Skill

Use when adding a new SDK example notebook to `sdk/` in the vidbyte-cookbook repo, or when updating an existing one.

---

## What a cookbook example is

Each `sdk/<name>/` folder is exactly **one Jupyter notebook** that rebuilds a
well-known production agentic system minimally using `vidbyte-sdk`. The
notebook teaches the user both what the real system does and how to replicate
its load-bearing architecture with the SDK. It is *not* a feature showcase —
it is a working implementation of a real-world system.

---

## SDK knowledge required before writing

Always read these before writing or editing any notebook:

- `vidbyte-sdk/skills/usage/available_tools.md` — full built-in tool catalog
- `vidbyte-sdk/skills/vidbyte-sdk/middleware.md` — all 13+ built-in middlewares
- `vidbyte-sdk/skills/usage/available_features.md` — pipelines, context, prompts, etc.
- `vidbyte-sdk/skills/usage/create_agent.md` — full Agent constructor reference

Key points to internalize:
- Import as `vidbyte`, package name is `vidbyte-sdk`
- Filesystem tools need `FileSystemToolConfig(root=..., allow_write=bool)` — not a bare constructor
- Code search tools (`GrepTool`, `GlobTool`, `PatchTool`) take `root_dir` as first positional arg
- `PermissionPolicy.allow_all()` is the factory for WRITE+EXECUTE access
- Middleware: `TokenBudgetMiddleware(max_tokens=N)`, `CostBudgetMiddleware(max_cost_usd=N)`, `RuntimeLimitMiddleware(max_iterations=N, max_elapsed_seconds=N)`, `LoopDetectionMiddleware()`, `AuditLogMiddleware()`, `ModelRetryMiddleware()`
- `reply.content` is the text output; `reply.metadata["structured"]` is the typed output when `output_schema` is set

---

## Required notebook structure (7 sections, in order)

Every notebook must have exactly these sections, in this order. Each is a
markdown cell followed by one or more code cells.

### 0. Title + intro (markdown only)

- Name and one-line description of the production system being rebuilt
- A brief architecture diagram (ASCII, in a code block)
- A bullet list of the SDK primitives this notebook showcases
- `> Before running: copy .env.example to .env at the repo root and add your provider key.`

### 1. Environment & constants

**Markdown:** Explain every constant — what it controls and why it matters.

**Code:**
```python
%pip install -q vidbyte-sdk python-dotenv <any-other-deps>

import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv("../../.env")

PROVIDER = os.getenv("VIDBYTE_COOKBOOK_PROVIDER", "openai")
MODEL    = os.getenv("VIDBYTE_COOKBOOK_MODEL", "gpt-4.1")
# ... other constants with inline comments
assert os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"), "..."
```

### 2. System prompt

**Markdown:** Explain *why* this agent needs a custom system prompt, what
operating procedure it encodes, and what the reader can change to adapt it.

**Code:** Define the system prompt string. One variable, well-commented.

### 3. Tools

**Markdown:** Explain the tool set — both the prebuilt SDK tools being used
and any custom `@tool` functions, and why each one is needed for this system.

**Code:** Import prebuilt tools + define custom `@tool` functions. Use the
**real SDK built-ins** where they fit the task; only write custom `@tool`
functions for logic the built-ins cannot express. Minimize lines.

Key built-ins to consider:
- `from vidbyte.tools.filesystem import ReadTextTool, WriteTextTool, ListDirTool, TreeTool, FindTool`
  - Requires `FileSystemToolConfig(root=WORKSPACE, allow_write=True/False)`
- `from vidbyte.tools.builtins.code_search import GlobTool, GrepTool`
  - Requires `root_dir=WORKSPACE`
- `from vidbyte.tools.builtins.editing import PatchTool`
  - Requires `root_dir=WORKSPACE`
- `from vidbyte import tool` for custom functions

### 4. Middleware

**Markdown:** Explain what middleware is in the SDK (deterministic runtime
policy, not visible to the model), and why this particular system benefits
from the middleware being added. Be specific about what each middleware guards.

**Code:** Instantiate a middleware list. Always include at least one budget
guard and one observability/safety guard. Common choices:

```python
from vidbyte.middleware import (
    TokenBudgetMiddleware,
    CostBudgetMiddleware,
    RuntimeLimitMiddleware,
    LoopDetectionMiddleware,
    AuditLogMiddleware,
    ModelRetryMiddleware,
)

middleware = [
    TokenBudgetMiddleware(max_tokens=50_000),
    CostBudgetMiddleware(max_cost_usd=0.50),
    RuntimeLimitMiddleware(max_iterations=25, max_elapsed_seconds=180.0),
    LoopDetectionMiddleware(),
    ModelRetryMiddleware(max_retries=3),
]
```

### 5. Constructing the agent

**Markdown:** Explain the agent's requirements — what runtime, what
permission policy, and what context algorithm (if any) the task demands.
Then wire the previous sections together.

**Code:**
```python
from vidbyte import BaseAgent
from vidbyte.tools.security import PermissionPolicy

agent = BaseAgent(
    name="...",
    system_prompt=SYSTEM_PROMPT,
    provider=PROVIDER,
    model_name=MODEL,
    tools=[...],                          # from Section 3
    middleware=middleware,                 # from Section 4
    permission_policy=PermissionPolicy.allow_all(),  # if WRITE tools present
    max_iterations=25,
    # trace_option=... if continual trace is relevant
)
```

### 6. Running the agent + example prompts

**Markdown:** Explain how to run the agent and what to expect. Give 3–5
real-world example prompts that show the breadth of what the system can handle.

**Code:** Run at least two of those examples end-to-end, printing `reply.content`.
Include a cell that inspects any trace or structured output artifact.

### 7. Example output

**Markdown:** A realistic example output — either as a literal markdown block
or as cells that print a sample response. This sets reader expectations and
makes the notebook feel real even before someone runs it.

---

## Style rules

- No standalone demo-repo setup cells (no "create workspace/seed files" boilerplate — if the agent needs a test target, create it inline in the env cell or as part of a prompt)
- Never write `%pip install` in multiple cells — one install cell at the top
- Prefer real SDK built-ins over hand-written `@tool` equivalents whenever the built-in exists
- Keep code cells short and purposeful — one concept per cell
- Every markdown cell must teach something, not just announce the next code cell
- The notebook must be runnable top-to-bottom on a clean Python 3.11+ environment with a valid `.env`

---

## Things to remember

- `FileSystemToolConfig(root=..., allow_write=True)` is required for all filesystem tools — never instantiate them bare
- `GrepTool` and `GlobTool` take `root_dir` positionally
- `PermissionPolicy.allow_all()` is the correct factory when WRITE or EXECUTE tools are in the list
- The `run()` method is sync; use it from notebooks (not `arun()` which needs async context)
- `reply.metadata["structured"]` holds `output_schema` typed output
- `reply.metadata["trace"]` and `agent.last_trace` hold the continual-trace artifact
