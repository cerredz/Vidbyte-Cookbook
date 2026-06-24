# Design Doc: Sakana Fugu — multi-agent orchestration behind one model API

**Status:** Draft
**Author:** Claude
**Created:** 2026-06-22
**Last Updated:** 2026-06-24

---

## 1. Overview

Sakana Fugu is a product (announced 2026-06-22) that presents a *full multi-agent
orchestration system as a single model API*. You call one endpoint; internally a
learned orchestrator decides whether to answer directly or to assemble a team of
expert models drawn from a swappable, multi-vendor pool, then synthesizes their
work into one answer. Its headline shape is **two models, one API**: a fast
default (`Fugu`) and a max-quality tier (`Fugu Ultra`), both behind the same
`run` call, with an opt-out mechanism for compliance/privacy. This cookbook
example — `sdk/sakana-fugu/sakana_fugu.ipynb` — rebuilds that load-bearing
architecture minimally with the Vidbyte SDK, following the cookbook's existing
"rebuild a production agentic system in one notebook" format.

The implementation is intentionally reduced to the orchestration skeleton: a
single `Fugu` facade class with exactly two methods — `run` (the public
single-model API) and `orchestrate` (the internal route + assemble + synthesize
step). Everything else is inlined.

---

## 2. Goals & Non-Goals

### Goals
- Add one self-contained cookbook notebook that faithfully rebuilds Fugu's
  *load-bearing* architecture: a single-model facade, a learned route (direct
  vs. delegate), a swappable multi-vendor pool, a synthesize step over the
  team's outputs, two tiers (Fugu / Fugu Ultra), and agent opt-out.
- Keep the `Fugu` class down to just `run` and `orchestrate` — no subtask
  decomposition, no dispatch/resolve helpers, no direct-solve helper, no
  verbose tracer, and no `build_fugu()` factory. The notebook constructs the
  agents inline and calls `fugu.run(...)` directly.
- Use the minimal real `vidbyte-sdk` primitive set needed for the product shape:
  `BaseAgent`, `@tool`, `output_schema`, and budget/runtime/retry middleware.
- Keep the implementation minimal — the entire notebook is one executable code
  cell — per the user's explicit "one Jupyter notebook cell, one code block" ask.
- Be runnable top-to-bottom with a single `OPENAI_API_KEY`; only the OpenAI
  pool member is callable with that one key.
- Keep the folder as a single-notebook cookbook example and update both index READMEs.
- Ship a deterministic verification script that tests the orchestration logic
  (routing, synthesize, opt-out, tiers, availability gating) with fake agents —
  no live model calls.

### Non-Goals
- Training or imitating a real "orchestration model." Our orchestrator is a
  standard LLM prompted to emit a routing plan; we rebuild the *system
  architecture*, not Sakana's learned coordinator weights (Trinity/Conductor).
- An OpenAI-compatible HTTP server / endpoint. The "single API" is modeled as a
  single Python method (`Fugu.run`), matching the other cookbook notebooks.
- Benchmark reproduction, billing tiers, or subscription/pay-as-you-go logic.
- Streaming, persistent state, or a UI.
- Route-around / runtime failover. Providers whose API keys are absent are
  simply not part of the available team for a given call — there is no
  re-assignment machinery. (Earlier iterations had this; it was removed to keep
  the class to `run` + `orchestrate`.)
- Subtask decomposition / per-subtask model assignment. In `delegate` mode the
  whole request is handed to every available expert; the orchestrator no longer
  emits a subtask list.
- Recursive self-call. Removed with the subtask logic.

---

## 3. Background & Context

- **Why now:** The product launched 2026-06-22 and is trending; the cookbook's
  premise is rebuilding well-known production agentic systems, so Fugu is a
  timely, on-format addition.
- **Problem it solves (for the reader):** Multi-agent orchestration is usually
  wired by hand. The notebook teaches both *what Fugu does* and *how little code
  the load-bearing skeleton takes* on the Vidbyte SDK.
- **Current state (base = `main`):** `sdk/` contains `droid/`, `deep-research/`,
  `sierra-support/`, and `self-refine/`, each one notebook; `docs/design/`
  already exists. `deep-research` and `self-refine` are the closest analogs —
  `deep-research` is a planner → researchers → synthesizer pipeline with
  `output_schema`; `self-refine` is a plain-Python class orchestrator
  (`SelfRefineLoop`) with small named methods and a `@dataclass` result. Fugu
  follows `self-refine`'s class-orchestrator house style but is stripped to a
  single `orchestrate` method.
- **Constraints/dependencies:** The cookbook skill mandates a self-contained
  notebook with budget + safety middleware, real SDK built-ins, and clean
  top-to-bottom execution on Python 3.11+ with one provider key. `vidbyte-sdk`
  is imported as `vidbyte`; providers supported include `openai`, `anthropic`,
  `gemini`, `xai`, `deepseek`, and more. Verified SDK signatures are taken from
  the merged `self-refine` notebook (e.g. `CostBudgetMiddleware(max_spend_usd=,
  cost_per_million_tokens=)`, `RuntimeLimitMiddleware(max_model_calls=,
  max_elapsed_seconds=)`), which supersede the skill doc's stale examples.

---

## 4. Requirements

### Functional Requirements
1. The notebook MUST expose a single facade, `Fugu.run(prompt) -> str`, that
   returns one answer — the multi-agent machinery never surfaces to the caller.
2. A **learned orchestrator** (`BaseAgent` with `output_schema`) MUST decide per
   request between `direct` (answer with one model) and `delegate` (assemble a
   team). Routing MUST come from the model's structured output, not a hardcoded
   keyword predicate.
3. The system MUST hold a **swappable, multi-vendor pool** of `BaseAgent`s keyed
   by specialty, each configured with a distinct `provider`/`model_name`. Adding
   or swapping a model MUST be a one-line change to the pool definition.
4. In `delegate` mode, the system MUST call every **available** pool expert on
   the request and then **synthesize** their labeled outputs into one answer.
5. If *no* pool model is available, `Fugu.run` MUST raise a clear, explicit error
   (not return `""` or a misleading success).
6. **Opt-out:** The caller MUST be able to exclude specific pool members (by key)
   for privacy/compliance; excluded members MUST never be called.
7. **Two tiers:** `Fugu` (fast: synthesize once, no verification) and
   `Fugu Ultra` (`ultra=True`: add a verification/critique pass over the
   synthesized answer). Both MUST be the same class behind the same `run` API.
8. The notebook MUST construct the `Fugu` instance inline and call
   `fugu.run(...)` directly — no `build_fugu()` factory.

### Non-Functional Requirements
- **Minimalism:** One notebook cell; the `Fugu` class has only `__init__`,
  `run`, and `orchestrate`. Prefer SDK built-ins over custom code.
- **Cost/latency control:** Every SDK agent (orchestrator, pool members,
  synthesizer, verifier) MUST run under budget + runtime middleware so one
  request cannot run away. `ModelRetryMiddleware` is attached for transient
  provider errors.
- **Testability:** The orchestration core MUST be exercisable with fake,
  duck-typed agents and no network/model/SDK dependency, so the Phase 5 script is
  deterministic and offline. The cell's live SDK construction is guarded by
  `try/except ImportError` so the offline harness can exec the same cell.
- **Honesty:** The notebook MUST clearly state what is real (architecture) vs.
  stubbed (the "learned coordinator" is just a prompted LLM; non-OpenAI vendors
  are availability-gated), per cookbook norms.

---

## 5. High-Level Design

The notebook builds a single `Fugu` facade class over three kinds of SDK
`BaseAgent`s plus a model pool:

- **Orchestrator** — *the "Fugu model."* A `BaseAgent` with
  `output_schema=OrchestrationPlan`. Given a prompt it returns a typed plan with
  just `mode` (`direct`/`delegate`) and `reasoning`.
- **Pool** — a list of `PoolModel` records (`key`, `provider`, `model`, `agent`),
  each a `BaseAgent` on a distinct vendor (`anthropic` reasoning, `openai`
  coding, `gemini` long-context, `deepseek` fast). "The world's best models,"
  entirely swappable by editing the list. Pool members carry the proven
  keyless Wikipedia `search`/`read_article` tools so delegated work produces
  grounded output.
- **Synthesizer** — a `BaseAgent` that merges worker outputs into one answer.
- **Verifier** (Ultra only) — a `BaseAgent` that critiques and finalizes the
  synthesized answer.

`Fugu.run` delegates to `orchestrate`, which routes internally and returns one
string:

```
                       +--------------------------- Fugu.run(prompt) --------------------------+
                       |                                                                       |
  prompt --> ORCHESTRATOR|  plan.mode == "direct"   -->  first available model  ----------> answer
   (one    (output_schema|                                                                       |
    API)    = Plan)     |  plan.mode == "delegate" --> for each available pool expert:          |
                       |        expert.agent.run(prompt) -> labeled output                      |
                       |        gather outputs --> SYNTHESIZER --> draft                        |
                       |        if ultra: --> VERIFIER --> final                               |
                       +---------------------------------------------------------------------+
               pool = [anthropic:reasoning, openai:coding, gemini:long_context, deepseek:fast]
               available = (key not opted out) AND (provider API key present)
```

**Key design decisions:**
- **Learned routing via `output_schema`, not `ConditionalPipeline`.** Fugu's
  routing is a model decision; `ConditionalPipeline`'s predicate is
  synchronous/keyword-based and can't express "the model decides whether to
  assemble a team." We read the orchestrator's structured plan.
  (`MapReducePipeline` is the closest static analog and is named in the
  narrative as the "fixed-team" version.)
- **Class orchestrator with one `orchestrate` method, not a pipeline** — matches
  the `self-refine` house style but reduced to a single internal method. `run`
  is a thin public wrapper over `orchestrate`.
- **Availability gating drives the demo.** With only `OPENAI_API_KEY`, the
  anthropic/gemini/deepseek experts are "unavailable" and only the OpenAI expert
  is called in `delegate` mode — runnable with one key.
- **Availability is a plain env-var lookup** (`PROVIDER_ENV` dict) inside
  `orchestrate`, so the core has *zero* SDK import at definition time and the
  test harness can exec it offline. The narrative points to
  `ProviderModelRegistry.get_api_key_env_var` as the SDK-native equivalent.
- **Tiers are one flag** (`ultra`) on one class — matching "both models, one API."
- **Duck-typed pool agents.** `Fugu` only calls `.run(str).content` on pool
  members, so tests inject fakes.

---

## 6. Detailed Design

The deliverable is one notebook with exactly one executable code cell. That cell
is marked with a leading `# [fugu-core]` sentinel comment so the verification
script can exec it offline. Top-level definitions import only `os`,
`dataclasses`, `typing`, and `pydantic`; the live SDK construction
(`import vidbyte`, building the agents, and calling `fugu.run(...)`) sits in a
`try/except ImportError` block at the bottom of the same cell, so tests can
exercise `Fugu` with fakes without importing `vidbyte` or making model calls,
while a real notebook run executes the whole cell top-to-bottom.

### 6.1 Schemas (`# [fugu-core]`)

**File(s):** `sdk/sakana-fugu/sakana_fugu.ipynb`
**Type:** New

#### What it does
Typed boundary for the orchestrator's routing decision.

#### Interface / API
```python
from pydantic import BaseModel, Field

class OrchestrationPlan(BaseModel):
    mode: str = Field(description='Exactly "direct" (one model) or "delegate" (assemble a team).')
    reasoning: str = Field(description="One sentence: why this route.")
```
`mode` is a value-constrained `str` (not `Literal`) to match the proven house
structured-output pattern. There is no `Subtask` model and no `subtasks` field —
the orchestrator no longer decomposes the request.

#### Edge Cases & Error Handling
- Provider that doesn't support / fails structured output → `orchestrate` reads
  `reply.metadata["structured"]`; if absent/invalid, falls back to a `direct`
  plan rather than crashing.

### 6.2 PoolModel record (`# [fugu-core]`)

**File(s):** same notebook
**Type:** New

#### What it does
Binds a specialty key to a vendor, model id, and a runnable agent.

#### Interface / API
```python
from dataclasses import dataclass
from typing import Any

@dataclass
class PoolModel:
    key: str        # specialty the orchestrator routes to
    provider: str   # vendor, e.g. "anthropic"
    model: str      # model id, e.g. "claude-sonnet-4-6"
    agent: Any      # anything with .run(str) -> reply(.content); a BaseAgent in the notebook, a fake in tests
```

### 6.3 `Fugu` facade class (`# [fugu-core]`)

**File(s):** same notebook
**Type:** New

#### What it does
The single-model facade. Orchestrates internally; returns one answer. The class
has only `__init__`, `run`, and `orchestrate` — all routing, dispatch,
synthesis, and verification happen inline inside `orchestrate`.

#### Interface / API
```python
PROVIDER_ENV = {
    "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY", "xai": "XAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
}

class Fugu:
    def __init__(self, orchestrator, pool, synthesizer, verifier=None, *, ultra=False, exclude=()): ...
    def run(self, prompt: str) -> str: ...          # public single-model API (thin wrapper)
    def orchestrate(self, prompt: str) -> str: ...  # route + assemble + synthesize (+ verify if ultra)
```

#### Logic / Algorithm
`run(prompt)` → `return self.orchestrate(prompt)`.

`orchestrate(prompt)`:
1. Try to read a structured `OrchestrationPlan` from
   `self.orchestrator.run(prompt).metadata.get("structured")` (coerce via
   `model_validate` if it is a dict); on any missing/invalid payload, fall back
   to `OrchestrationPlan(mode="direct", reasoning="fallback: no structured plan")`.
2. `available = [m for m in self.pool if m.key not in self.exclude and
   os.getenv(PROVIDER_ENV.get(m.provider, ""))]`.
3. If `not available` → raise `RuntimeError("Fugu: no available models in pool")`.
4. If `plan.mode != "delegate"` → `return available[0].agent.run(prompt).content`
   (direct: one model).
5. `outputs = [f"[{m.key}] {m.agent.run(prompt).content}" for m in available]`.
6. `answer = self.synthesizer.run(<prompt + labeled expert outputs>).content`.
7. If `self.ultra and self.verifier` →
   `return self.verifier.run(<prompt + draft answer>).content`; else `return answer`.

#### Edge Cases & Error Handling
- Empty pool / all opted out / no keys → step 3 raises `RuntimeError` (Req 5).
- Structured-output failure → step 1 safe `direct` fallback, never a crash.
- `delegate` with only one available expert → step 5 produces a single labeled
  output and synthesis still runs.

### 6.4 System prompts

**File(s):** same notebook
**Type:** New

Three compact prompt strings in the same cell: ORCHESTRATOR (routing policy +
the list of specialty keys — `reasoning`, `coding`, `long_context`, `fast`;
prefer `direct` for simple asks, `delegate` for hard/multi-domain ones),
SYNTHESIZER (merge expert outputs into one authoritative answer, reconcile
conflicts), VERIFIER (Ultra: check the answer against the request, fix errors,
return the final answer only).

### 6.5 Pool, agents, tools & middleware construction

**File(s):** same notebook, same `# [fugu-core]` cell.
**Type:** New

The bottom of the cell (inside a `try/except ImportError` block so offline test
exec skips it) imports the minimal SDK surface, defines the keyless Wikipedia
tools (`search`, `read_article`), builds the orchestrator/synthesizer/verifier
`BaseAgent`s, builds the pool, constructs a `Fugu`, and calls `fugu.run(...)`.
Middleware (verified signatures) attached to each agent:
```python
[ TokenBudgetMiddleware(max_tokens=...),
  CostBudgetMiddleware(max_spend_usd=..., cost_per_million_tokens=...),
  RuntimeLimitMiddleware(max_model_calls=..., max_elapsed_seconds=...),
  ModelRetryMiddleware(max_attempts=...) ]
```
The orchestrator/synthesizer/verifier use env `PROVIDER`/`MODEL`; pool members
name real vendors so availability gating is meaningful.

### 6.6 Index README updates

**File(s):** `README.md` (root), `sdk/README.md`
**Type:** Modified

Add a `sakana-fugu` row to both example-index tables and the root Repository
Layout tree, matching existing tone and the trademark/independent-reimplementation
disclaimer.

---

## 7. Data Model Changes

N/A — no database, schema, or persistent store. The only "schema" is the
in-notebook Pydantic model `OrchestrationPlan` defined in §6.1, used purely as
the orchestrator's structured-output boundary.

---

## 8. API Changes

N/A — no HTTP/service API. The "single model API" is modeled as the in-process
`Fugu.run(prompt) -> str` method (§6.3), consistent with the other cookbook
notebooks, which expose plain Python entry points rather than endpoints.

---

## 9. File Change Manifest

| Action | File Path | Reason |
|--------|-----------|--------|
| CREATE | `docs/design/sakana-fugu.md` | This design doc (first commit on the branch). |
| CREATE | `sdk/sakana-fugu/sakana_fugu.ipynb` | The cookbook notebook rebuilding Sakana Fugu. |
| CREATE | `scripts/test_sakana_fugu.py` | Deterministic offline verification of the orchestration core. |
| MODIFY | `sdk/README.md` | Add `sakana-fugu` to the SDK examples index table. |
| MODIFY | `README.md` | Add `sakana-fugu` to the root Example Index table + layout tree. |

Counts: **3 created, 2 modified, 0 deleted.**

---

## 10. Testing Plan

The verification script `scripts/test_sakana_fugu.py` loads the notebook as JSON,
execs only the single `# [fugu-core]` cell (offline, no SDK), and drives `Fugu`
with **fake agents**. A `FakeAgent` returns a canned `reply` whose `.content` is
a fixed string and (for the orchestrator) whose `.metadata["structured"]` is a
chosen `OrchestrationPlan`. Availability is controlled by setting/clearing
provider env vars inside each test.

### Unit Tests
- `Fugu.run` → `it('returns a single string in direct mode without synthesizing')` — [Edge Case]
- `Fugu.run` → `it('calls every available expert and synthesizes in delegate mode')` — happy path
- `Fugu.run` → `it('skips experts whose provider key is absent')` — [Hidden Assumption]
- `run` (ultra) → `it('runs the verifier pass when ultra=True and not when ultra=False')` — [Edge Case]
- `orchestrate` → `it('falls back to a direct plan when structured output is missing/invalid')` — [Silent Failure]
- `run` → `it('raises RuntimeError when no pool model is available')` — [Silent Failure]
- `run` → `it('never calls an opted-out (excluded) member')` — [Hidden Assumption]

### Integration Tests
- End-to-end (fakes): a `delegate` plan with a pool of three vendors
  (`reasoning`(anthropic, key absent), `coding`(openai, key present),
  `long_context`(gemini, key absent)) — with only `OPENAI_API_KEY` set, assert
  only the OpenAI expert is called and the synthesizer is called once with a
  labeled output. This is the headline scenario the notebook's usage line is
  meant to exercise.
- Silent-failure path: when the orchestrator emits `delegate` but every provider
  key is cleared, `run` raises rather than the synthesizer being called with an
  empty list and returning a hollow answer.
- A plan constructed via `OrchestrationPlan.model_validate(...)` (as the SDK
  would produce) round-trips and `delegate` runs end-to-end.

### Manual / QA Test Cases
1. Given only `OPENAI_API_KEY`, running the cell calls only the OpenAI expert in
   `delegate` mode and prints one coherent final answer — [Hidden Assumption].
2. Given `exclude=("coding",)`, the coding expert is never called —
   [Hidden Assumption].
3. Given a simple factual prompt, `mode` is `direct` and only one model is
   consulted — [Edge Case].
4. Given `ultra=True` vs `ultra=False` on the same delegate prompt, the Ultra
   run performs an extra verifier call — [Edge Case].

---

## 11. Dependencies & External Services

| Dependency | Version / Endpoint | Purpose | Risk |
|------------|--------------------|---------|------|
| `vidbyte-sdk` | current repo surface | `BaseAgent`, `output_schema`, middleware | Pre-release API drift; mitigated by using only documented/verified primitives. |
| `pydantic` | 2.x | Structured-output schema | Low; used by sibling notebooks. |
| `python-dotenv` | any | Load `.env` | Low. |
| `requests` | any | Keyless Wikipedia tools for pool members | Low; reused verbatim from siblings. |
| OpenAI API | `OPENAI_API_KEY` | Default provider for orchestrator/synthesizer/pool | Cost; mitigated by budget/runtime middleware. |
| Anthropic/Gemini/xAI/DeepSeek APIs | respective keys (optional) | Real multi-vendor pool; absent keys leave the expert unavailable | None when absent — absence is intended. |
| stdlib `json` | — | Test harness reads the notebook (no nbformat dep) | Low; JSON parse only. |

---

## 12. Rollout & Deployment

- **Feature flags:** None.
- **Breaking change:** No — purely additive (one new folder + README rows).
- **Deployment order:** N/A (documentation/example repo).
- **Rollback:** Revert the branch / delete `sdk/sakana-fugu/` and the README rows.
- **Process:** Worktree branch off `origin/main`; design-doc commit first, then
  notebook, then test script, then README updates; open a PR targeting `main`
  with this doc as the body.

---

## 13. Open Questions

- [x] **Folder name** → `sdk/sakana-fugu/` (confirmed; named after the rebuilt system).
- [x] **Base branch** → branch off `origin/main`, PR into `main` (confirmed;
  `main` already contains the cookbook content — local `main` was merely stale).
- [x] **Class surface** → `run` + `orchestrate` only; no subtask/resolve/dispatch/
  solve_directly/_say/build_fugu (confirmed by review feedback on PR #7).
- [ ] **Pool vendor list / model ids.** Proposed: anthropic→reasoning,
  openai→coding, gemini→long_context, deepseek→fast. Illustrative only; only
  OpenAI runs in the default demo. Confirm exact model ids to name.

## 14. Alternatives Considered

### Alternative 1: `BaseAgent` with `ActorRuntime(dynamic_actors=True)`
- **What:** Use the SDK's built-in actor-model swarm — one agent that dynamically
  spawns sub-actors — as Fugu.
- **Why rejected:** It's the most literal "one agent orchestrating many," but it
  is *strictly incompatible with middleware* (the cookbook format requires budget
  + safety middleware) and uses fixed personas on a single configured model. It
  cannot express a *multi-vendor* swappable pool. Mentioned in the notebook's
  "what production adds / turn it up" section as the swarm upgrade path.

### Alternative 2: `ConditionalPipeline` + `MapReducePipeline` only
- **What:** Route with `ConditionalPipeline` (predicate) into a fixed
  `MapReducePipeline` (map to specialists, reduce to synthesis).
- **Why rejected:** `ConditionalPipeline`'s predicate is synchronous and keyword-
  based — it can't model a *learned* decision to assemble a team. We instead
  read the orchestrator's `output_schema` plan. `MapReducePipeline` is
  referenced in the narrative as the "static fixed-team" cousin of Fugu's
  dynamic team assembly.

### Alternative 3: A real OpenAI-compatible HTTP endpoint
- **What:** Stand up a FastAPI `/v1/chat/completions` server wrapping `Fugu`.
- **Why rejected:** Out of format. Every cookbook notebook exposes an in-process
  Python entry point, not a server; an endpoint adds infra and obscures the
  architecture the notebook exists to teach. Noted as a "production adds" item.

### Alternative 4: Put the core in a `.py` module beside the notebook
- **What:** Ship `sdk/sakana-fugu/fugu.py` and import it from the notebook + tests.
- **Why rejected:** The cookbook skill mandates *exactly one notebook* per folder.
  Instead, the single notebook cell is marked `# [fugu-core]` and the test harness
  execs that cell from the `.ipynb`, keeping the single-notebook rule while
  staying testable.

### Alternative 5: Keep subtask decomposition, route-around, and recursion
- **What:** The earlier `Fugu` with `Subtask`, `_resolve`/`_dispatch`/`_run_subtask`,
  `_solve_directly`, `_say`, recursive self-call, and a `build_fugu()` factory.
- **Why rejected:** Review feedback on PR #7 asked to reduce the class to a
  "multi-agent orchestration" skeleton with only `orchestrate` and `run`. All
  subtask / resolve / dispatch / direct-solve / verbose-tracer / factory
  machinery was removed and inlined into `orchestrate`.

---

END OF DESIGN DOC
