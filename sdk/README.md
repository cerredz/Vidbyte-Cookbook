# Vidbyte SDK Examples — production agentic systems, rebuilt minimal

Each folder here is **one Jupyter notebook** that rebuilds a well-known
production agentic system from the ground up in a few hundred lines, using
[`vidbyte-sdk`](https://pypi.org/project/vidbyte-sdk/) (`pip install
vidbyte-sdk`, imported as `vidbyte`).

These are not toy demos of SDK features — each notebook starts from what the
real system actually does, identifies the load-bearing architecture, and
walks you through building a minimal but honest version of it. They won't be
perfect replicas; they will teach you the shape of the real thing.

| Notebook | Rebuilds | The architecture you'll build |
|---|---|---|
| [`droid/droid.ipynb`](droid/droid.ipynb) | **Factory's Droid** — autonomous software engineering agents | The explore → reproduce → fix → verify loop: file and shell tools jailed to a workspace, a strict operating procedure, independent verification, and a structured run report via `TraceOption.continual(ActionTrace)`. |
| [`deep-research/deep_research.ipynb`](deep-research/deep_research.ipynb) | **OpenAI Deep Research** — long-form research with citations | The planner → researchers → synthesizer pipeline: typed stage boundaries via `output_schema`, search/read tools, and source-attributed findings so the writer can't make uncited claims. |
| [`sierra-support/sierra_support.ipynb`](sierra-support/sierra_support.ipynb) | **Sierra** — enterprise customer-service agents | Grounded actions over business systems, two-layer guardrails (policy in the prompt *and* hard limits in tool code), structured human escalation, and a code-level audit log. |
| [`self-refine/self_refine.ipynb`](self-refine/self_refine.ipynb) | **Reflexion / Self-Refine** — a self-improving multi-agent loop | The plan → execute → critique → re-plan loop as three named agents: a planner that emits typed subgoals, a tool-using worker that re-attempts fresh each round and emits a `handoff`, and a devil's-advocate debator whose typed fault list is the loop's stop signal. |

## Running a notebook

Each notebook is fully self-contained — it installs its own dependencies in
the first cell. You need Python 3.11+, Jupyter, and a model provider key:

```bash
cp .env.example .env        # at the repo root; add OPENAI_API_KEY
jupyter lab sdk/droid/droid.ipynb
```

Run the cells top to bottom. Every notebook ends with a "what the production
system adds" section and concrete things to try next.

> The systems referenced (Factory, OpenAI, Sierra) are trademarks of their
> respective owners. These notebooks are independent, minimal educational
> reimplementations of publicly described architectures — not affiliated
> with or endorsed by those companies.
