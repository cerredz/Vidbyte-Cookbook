# Vidbyte Cookbook

Practical, runnable examples for building with **Vidbyte** — both the
**Vidbyte API** (the learning platform: quizzes, exams, roadmaps, learner
state) and the **Vidbyte SDK** (`vidbyte-sdk`, a Python framework for building
agents with tools, managed context windows, structured output, tracing, and
swappable runtimes).

## The Two Surfaces

| Surface | What it is | When you reach for it |
|---|---|---|
| **Vidbyte API** | REST + MCP access to the learning platform: generate quizzes, exams, roadmaps, and quick-hits; read and write persistent learner state (mastery, review schedule, gap map). | You're building a product or agent that needs durable learning features — content generation backed by learning science, plus per-user memory of what the learner actually knows. |
| **Vidbyte SDK** | A Python agent framework: `Agent`/`BaseAgent`, `@tool`, `ContextManager` and context primitives, context-window algorithms, structured output via `output_schema`, continual trace artifacts, and runtimes (linear, MCTS search, actor model). | You're building the agent itself and want production-grade context management and orchestration without wiring it by hand. |

## What's in the SDK examples

The `sdk/` examples have one format and one premise: **rebuild a well-known
production agentic system, minimal and from the ground up, in a single
walkthrough notebook.** Systems like Factory's Droid or OpenAI's Deep
Research are large products, but the architecture that makes each of them
work fits in a few hundred lines — and building that skeleton yourself is the
fastest way to understand both the system and the SDK.

Each notebook narrates as it builds: what the real system does, which parts
are load-bearing, the minimal version of each part, a live end-to-end run,
and what the production system adds beyond the skeleton.

## Repository Layout

```
vidbyte-cookbook/
├── .env.example   # copy to .env — every notebook loads it
├── api/           # Vidbyte API examples — REST quickstarts and MCP integrations
└── sdk/           # one self-contained notebook per rebuilt system
    ├── droid/            # Factory-style autonomous software engineering agent
    ├── deep-research/    # OpenAI Deep Research-style planner/researcher/synthesizer
    └── sierra-support/   # Sierra-style guardrailed customer support agent
```

## Quickstart

```bash
# 1. Configure credentials once, at the repo root
cp .env.example .env   # add OPENAI_API_KEY (or Anthropic + provider overrides)

# 2. Open any notebook (Python 3.11+; first cell installs its dependencies)
jupyter lab sdk/droid/droid.ipynb

# 3. Run the cells top to bottom
```

## Example Index

| Example | Rebuilds | Core SDK pieces |
|---|---|---|
| [`sdk/droid`](sdk/droid/droid.ipynb) | Factory's **Droid** — an autonomous software engineer that takes a ticket, edits a repo, runs tests until green, and reports back | `@tool` file/shell tools, `max_iterations`, `TraceOption.continual(ActionTrace)` for the structured run report |
| [`sdk/deep-research`](sdk/deep-research/deep_research.ipynb) | OpenAI's **Deep Research** — decompose a question, research each thread, synthesize a cited report | `output_schema` typed stage boundaries, search/read tools, multi-agent pipeline |
| [`sdk/sierra-support`](sdk/sierra-support/sierra_support.ipynb) | **Sierra** — a customer-service agent that resolves real issues under hard policy with human escalation | tools as grounded actions, code-level guardrails, structured escalation, audit log |
| `api/` | — | REST and MCP quickstarts; see [`api/README.md`](api/README.md) for the roadmap. |

## Requirements

- Python **3.11+** and Jupyter
- A model provider API key (OpenAI or Anthropic)
- Optional: Vidbyte API credentials for live platform calls

## Status

This cookbook is pre-release and tracks the current `vidbyte-sdk` surface.
APIs may change before the first stable release. Licensing follows the
Vidbyte SDK's release licensing (TBD).

The production systems referenced in `sdk/` (Factory, OpenAI, Sierra) are
trademarks of their respective owners; the notebooks are independent,
minimal educational reimplementations of publicly described architectures,
not affiliated with or endorsed by those companies.

## Contributing

Each example should be: a single self-contained notebook, runnable in under
five minutes, honest about what's real vs. stubbed, and focused on rebuilding
one production system's load-bearing architecture. If you've rebuilt
something interesting with the Vidbyte SDK, we'd love a PR adding it here.
