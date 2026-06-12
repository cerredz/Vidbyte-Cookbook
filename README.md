# Vidbyte Cookbook

Practical, runnable examples for building with **Vidbyte** — both the
**Vidbyte API** (the learning platform: quizzes, exams, roadmaps, learner
state) and the **Vidbyte SDK** (`vidbyte-sdk`, a Python framework for building
agents with tools, managed context windows, structured output, tracing, and
swappable runtimes).

Every example here is a real-world setup, not a hello-world. The goal is to
show you how to use each surface *and* why you'd want to — what genuinely
valuable thing you can ship with it.

## The Two Surfaces

| Surface | What it is | When you reach for it |
|---|---|---|
| **Vidbyte API** | REST + MCP access to the learning platform: generate quizzes, exams, roadmaps, and quick-hits; read and write persistent learner state (mastery, review schedule, gap map). | You're building a product or agent that needs durable learning features — content generation backed by learning science, plus per-user memory of what the learner actually knows. |
| **Vidbyte SDK** | A Python agent framework: `Agent`/`BaseAgent`, `@tool`, `ContextManager` and context primitives, context-window algorithms, structured output via `output_schema`, continual trace artifacts, and runtimes (linear, MCTS search, actor model). | You're building the agent itself and want production-grade context management and orchestration without wiring it by hand. |

The strongest examples combine both: an agent built with the SDK that uses
the Vidbyte API as its tools — so the agent has real, persistent knowledge of
the learner instead of starting cold every session.

## Repository Layout

```
vidbyte-cookbook/
├── api/    # Vidbyte API examples — REST quickstarts and MCP integrations
└── sdk/    # Vidbyte SDK examples — real-world agent setups
    ├── study-agent/          # Spaced-repetition study coach (tools + learner state)
    ├── paper-to-quiz/        # Research paper → validated quiz (context primitives + structured output)
    └── socratic-tutor-swarm/ # Multi-agent Socratic tutor (actor runtime)
```

Each example folder is self-contained: its own `README.md`, a Jupyter
notebook, `requirements.txt`, and `.env.example`.

## Quickstart

```bash
# 1. Pick an example
cd sdk/study-agent

# 2. Install dependencies (Python 3.11+)
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env   # then fill in your model provider key

# 4. Open the notebook and run the cells top to bottom
jupyter lab study_agent.ipynb
```

Examples use real model providers (OpenAI, Anthropic, etc.) configured
through `.env`. Where an example talks to the Vidbyte API, it reads
`VIDBYTE_API_URL` / `VIDBYTE_API_KEY` from the environment and falls back to
a clearly-marked local stub when those are unset — so every example runs
end-to-end out of the box.

## Example Index

| Example | Surface | What it shows |
|---|---|---|
| [`sdk/study-agent`](sdk/study-agent/) | SDK + API | A spaced-repetition study coach: an agent whose tools read the learner's due reviews and mastery state, run a retrieval-practice session, and write results back to the scheduler. |
| [`sdk/paper-to-quiz`](sdk/paper-to-quiz/) | SDK + API | A two-stage pipeline that digests a research paper with `ContextManager` + `FileContextItem`, then emits a schema-validated quiz via `output_schema`. |
| [`sdk/socratic-tutor-swarm`](sdk/socratic-tutor-swarm/) | SDK | A Socratic tutor built on the `ActorRuntime`: a coordinator spawns specialized sub-actors (explainer, question-writer, misconception-checker) that collaborate on each turn. |
| `api/` | API | REST and MCP quickstarts — see [`api/README.md`](api/README.md) for the roadmap. |

## Requirements

- Python **3.11+**
- A model provider API key (OpenAI or Anthropic) for the SDK examples
- Optional: Vidbyte API credentials for live platform calls

## Status

This cookbook is pre-release and tracks the current `vidbyte-sdk` surface.
APIs may change before the first stable release; each example pins what it
needs in its own `requirements.txt`. Licensing follows the Vidbyte SDK's
release licensing (TBD).

## Contributing

Each example should be: self-contained, runnable in under five minutes,
honest about what is live vs. stubbed, and focused on one real-world job. If
you build something useful with Vidbyte, we'd love a PR adding it here.
