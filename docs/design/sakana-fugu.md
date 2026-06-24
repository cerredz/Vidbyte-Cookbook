# Design Doc: Sakana Fugu — multi-agent orchestration behind one model API

**Status:** Draft
**Author:** Claude
**Created:** 2026-06-22
**Last Updated:** 2026-06-24

---

## 1. Overview

Sakana Fugu is a product (announced 2026-06-22) that presents a *full multi-agent
orchestration system as a single model API*. You call one endpoint; internally it
assembles a team of expert models drawn from a swappable, multi-vendor pool, runs
them on the request, and synthesizes their work into one answer. Its headline
shape is **two models, one API**: a fast default (`Fugu`) and a max-quality tier
(`Fugu Ultra`), both behind the same `run` call, with an opt-out mechanism for
compliance/privacy. This cookbook example —
`sdk/sakana-fugu/sakana_fugu.ipynb` — rebuilds that load-bearing architecture
minimally with the Vidbyte SDK, following the cookbook's existing "rebuild a
production agentic system in one notebook" format.

The implementation is intentionally reduced to the orchestration skeleton: a
single `Fugu` facade class with exactly two methods — `run` (the public
single-model API) and `orchestrate` (the internal assemble + synthesize step).
There is no routing plan, no subtask decomposition, no tools, no explicit
provider/model/budget configuration (the SDK defaults those), and no factory
function. The notebook constructs the agents inline and calls `fugu.run(...)`
directly.

---

## 2. Goals & Non-Goals

### Goals
- Add one self-contained cookbook notebook that faithfully rebuilds Fugu's
  *load-bearing* architecture: a single-model facade, a swappable multi-vendor
  pool, a synthesize step over the team's outputs, two tiers (Fugu / Fugu Ultra),
  and agent opt-out.
- Keep the `Fugu` class down to just `run` and `orchestrate`. No orchestration
  plan, no subtask decomposition, no dispatch/resolve helpers, no direct-solve
  helper, no verbose tracer, and no `build_fugu()` factory. The notebook
  constructs the agents inline and calls `fugu.run(...)` directly.
- Use the minimal real `vidbyte-sdk` primitive set: just `BaseAgent`. Provider,
  model, tool rounds, and budget/runtime middleware are not configured — the
  SDK's defaults are used.
- Keep the implementation minimal — the entire notebook is one executable code
  cell — per the user's explicit "one Jupyter notebook cell, one code block" ask.
- Be runnable top-to-bottom with a single `OPENAI_API_KEY`; only the OpenAI
  pool member is callable with that one key (availability gating).
- Keep the folder as a single-notebook cookbook example and update both index READMEs.
- Ship a deterministic verification script that tests the orchestration logic
  (synthesize, opt-out, tiers, availability gating) with fake agents — no live
  model calls.

### Non-Goals
- Training or imitating a real "orchestration model." We rebuild the *system
  architecture*, not Sakana's learned coordinator weights (Trinity/Conductor).
- An OpenAI-compatible HTTP server / endpoint. The "single API" is modeled as a
  single Python method (`Fugu.run`), matching the other cookbook notebooks.
- Benchmark reproduction, billing tiers, or subscription/pay-as-you-go logic.
- Streaming, persistent state, or a UI.
- A routing plan / direct-vs-delegate decision. Removed per review feedback —
  `orchestrate` always assembles the team.
- Subtask decomposition / per-subtask model assignment / recursive self-call.
  Removed with the plan logic.
- Tools (`search`/`read_article`). Removed per review feedback — experts run
  tool-free.
- Explicit provider/model/max_tool_rounds/budget configuration. Removed per
  review feedback — the SDK defaults these.
- Route-around / runtime failover. Providers whose API keys are absent are
  simply not part of the available team for a given call — there is no
  re-assignment machinery.

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
  `deep-research` is a planner → researchers → synthesizer pipeline; `self-refine`
  is a plain-Python class orchestrator (`SelfRefineLoop`) with small named
  methods and a `@dataclass` result. Fugu follows `self-refine`'s
  class-orchestrator house style but is stripped to a single `orchestrate`
  method and no structured-output routing.
- **Constraints/dependencies:** The cookbook skill mandates a self-contained
  notebook with real SDK built-ins and clean top-to-bottom execution on Python
  3.11+ with one provider key. `vidbyte-sdk` is imported as `vidbyte`; providers
  supported include `openai`, `anthropic`, `gemini`, `xai`, `deepseek`, and more.

---

## 4. Requirements

### Functional Requirements
1. The notebook MUST expose a single facade, `Fugu.run(prompt) -> str`, that
   returns one answer — the multi-agent machinery never surfaces to the caller.
2. The system MUST hold a **swappable, multi-vendor pool** of `BaseAgent`s keyed
   by specialty, each tagged with a `provider` for availability gating. Adding
   or swapping a model MUST be a one-line change to the pool definition.
3. `orchestrate` MUST call every **available** pool expert on the request and
   then **synthesize** their labeled outputs into one answer.
4. If *no* pool expert is available, `Fugu.run` MUST raise a clear, explicit
   error (not return `""` or a misleading success).
5. **Opt-out:** The caller MUST be able to exclude specific pool members (by key)
   for privacy/compliance; excluded members MUST never be called.
6. **Two tiers:** `Fugu` (fast: synthesize once, no verification) and
   `Fugu Ultra` (`ultra=True`: add a verification/critique pass over the
   synthesized answer). Both MUST be the same class behind the same `run` API.
7. The notebook MUST construct the `Fugu` instance inline and call
   `fugu.run(...)` directly — no `build_fugu()` factory.

### Non-Functional Requirements
- **Minimalism:** One notebook cell; the `Fugu` class has only `__init__`,
  `run`, and `orchestrate`. Provider, model, `max_tool_rounds`, and budget
  middleware are not set on the agents — the SDK's defaults apply. Brief 1-2
  line comments are dispersed through the cell.
- **Testability:** The orchestration core MUST be exercisable with fake,
  duck-typed agents and no network/model/SDK dependency, so the Phase 5 script is
  deterministic and offline. The cell's live SDK construction is guarded by
  `if __name__ == "__main__":` so the offline harness (which execs the cell with
  a non-`__main__` `__name__`) skips it.
- **Honesty:** The notebook MUST clearly state what is real (architecture) vs.
  stubbed (non-OpenAI vendors are availability-gated), per cookbook norms.

---

## 5. High-Level Design

The notebook builds a single `Fugu` facade class over a model pool plus two SDK
`BaseAgent`s:

- **Pool** — a list of `PoolModel` records (`key`, `provider`, `agent`), each a
  `BaseAgent` representing a specialty (`anthropic` reasoning, `openai` coding,
  `gemini` long-context, `deepseek` fast). "The world's best models," entirely
  swappable by editing the list. Pool agents are configured with the SDK's
  default provider/model and no tools.
- **Synthesizer** — a `BaseAgent` that merges worker outputs into one answer.
- **Verifier** (Ultra only) — a `BaseAgent` that critiques and finalizes the
  synthesized answer.

`Fugu.run` delegates to `orchestrate`, which assembles the team and returns one
string:

```
                       +--------------------------- Fugu.run(prompt) --------------------------+
                       |                                                                       |
  prompt --> orchestrate|  available = pool members whose provider key is present (and not     |
   (one                 |             opted out)                                               |
    API)                |  for each available expert: expert.agent.run(prompt) -> labeled out   |
                       |  gather outputs --> SYNTHESIZER --> draft                            |
                       |  if ultra: --> VERIFIER --> final                                    |
                       +---------------------------------------------------------------------+
               pool = [anthropic:reasoning, openai:coding, gemini:long_context, deepseek:fast]
               available = (key not opted out) AND (provider API key present)
```

**Key design decisions:**
- **No routing plan.** Earlier iterations had an orchestrator agent emit a
  `direct`/`delegate` plan via `output_schema`. Review feedback removed it:
  `orchestrate` always assembles the available team. This drops the
  `OrchestrationPlan` model, the orchestrator agent, and all structured-output
  machinery.
- **Class orchestrator with one `orchestrate` method, not a pipeline** — matches
  the `self-refine` house style but reduced to a single internal method. `run`
  is a thin public wrapper over `orchestrate`.
- **Availability gating drives the demo.** With only `OPENAI_API_KEY`, the
  anthropic/gemini/deepseek experts are "unavailable" and only the OpenAI expert
  is called — runnable with one key.
- **Availability is a plain env-var lookup** (`PROVIDER_ENV` dict) inside
  `orchestrate`, so the core has *zero* SDK import at definition time and the
  test harness can exec it offline.
- **SDK defaults for provider/model/budget.** The agents are constructed with
  `BaseAgent(name=..., system_prompt=...)` only — no `provider`, `model_name`,
  `max_tool_rounds`, or middleware is passed. The SDK's defaults apply, per
  review feedback.
- **Tiers are one flag** (`ultra`) on one class — matching "both models, one API."
- **Duck-typed pool agents.** `Fugu` only calls `.run(str).content` on pool
  members, so tests inject fakes.

---

## 6. Detailed Design

The deliverable is one notebook with exactly one executable code cell. That cell
is marked with a leading `# [fugu-core]` sentinel comment so the verification
script can exec it offline. Top-level definitions import only `os`,
`dataclasses`, and `typing` — no `pydantic` (no structured-output schema), no
`vidbyte`. The live SDK construction (`import vidbyte`, building the agents, and
calling `fugu.run(...)`) sits in an `if __name__ == "__main__":` block at the
bottom of the same cell, so tests can exercise `Fugu` with fakes without
importing `vidbyte` or making model calls, while a real notebook run
(`__name__ == "__main__"`) executes the whole cell top-to-bottom.

### 6.1 `PoolModel` record (`# [fugu-core]`)

**File(s):** `sdk/sakana-fugu/sakana_fugu.ipynb`
**Type:** New

#### What it does
Binds a specialty key to a provider (for availability gating) and a runnable
agent.

#### Interface / API
```python
from dataclasses import dataclass
from typing import Any

@dataclass
class PoolModel:
    key: str        # specialty, e.g. "reasoning"
    provider: str   # vendor whose API key gates this slot, e.g. "anthropic"
    agent: Any      # anything with .run(str) -> reply(.content); a BaseAgent in the notebook, a fake in tests
```

### 6.2 `Fugu` facade class (`# [fugu-core]`)

**File(s):** same notebook
**Type:** New

#### What it does
The single-model facade. Orchestrates internally; returns one answer. The class
has only `__init__`, `run`, and `orchestrate` — all team assembly, synthesis,
and verification happen inline inside `orchestrate`.

#### Interface / API
```python
PROVIDER_ENV = {
    "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY", "xai": "XAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
}

class Fugu:
    def __init__(self, pool, synthesizer, verifier=None, *, ultra=False, exclude=()): ...
    def run(self, prompt: str) -> str: ...          # public single-model API (thin wrapper)
    def orchestrate(self, prompt: str) -> str: ...  # assemble available experts + synthesize (+ verify if ultra)
```

#### Logic / Algorithm
`run(prompt)` → `return self.orchestrate(prompt)`.

`orchestrate(prompt)`:
1. `available = [m for m in self.pool if os.getenv(PROVIDER_ENV.get(m.provider, ""))]`
   (excluded members were already filtered out in `__init__`).
2. If `not available` → raise `RuntimeError("Fugu: no available experts in pool")`.
3. `outputs = [f"[{m.key}] {m.agent.run(prompt).content}" for m in available]`.
4. `answer = self.synthesizer.run(<prompt + labeled expert outputs>).content`.
5. If `self.ultra and self.verifier` →
   `return self.verifier.run(<prompt + draft answer>).content`; else `return answer`.

#### Edge Cases & Error Handling
- Empty pool / all opted out / no keys → step 2 raises `RuntimeError` (Req 4).
- `delegate` with only one available expert → step 3 produces a single labeled
  output and synthesis still runs.

### 6.3 System prompts

**File(s):** same notebook
**Type:** New

Three compact prompt strings in the same cell: SYNTHESIZER (merge expert outputs
into one authoritative answer, reconcile conflicts), VERIFIER (Ultra: check the
answer against the request, fix errors, return the final answer only), EXPERT
(a `{specialty}` expert template). The earlier ORCHESTRATOR prompt was removed
with the routing plan.

### 6.4 Pool, agents & usage (`if __name__ == "__main__"` block)

**File(s):** same notebook, same `# [fugu-core]` cell.
**Type:** New

The bottom of the cell (inside `if __name__ == "__main__":` so offline test exec
skips it) imports `BaseAgent`, builds the synthesizer/verifier `BaseAgent`s with
`BaseAgent(name=..., system_prompt=...)` only (SDK defaults for provider/model,
no middleware, no tools), builds the pool, constructs a `Fugu`, and calls
`fugu.run(...)`. Provider, model, `max_tool_rounds`, and budget middleware are
not set — the SDK's defaults apply, per review feedback.

### 6.5 Index README updates

**File(s):** `README.md` (root), `sdk/README.md`
**Type:** Modified

Add a `sakana-fugu` row to both example-index tables and the root Repository
Layout tree, matching existing tone and the trademark/independent-reimplementation
disclaimer.

---

## 7. Data Model Changes

N/A — no database, schema, or persistent store. There is no in-notebook Pydantic
model anymore (the `OrchestrationPlan` schema was removed with the routing plan).

---

## 8. API Changes

N/A — no HTTP/service API. The "single model API" is modeled as the in-process
`Fugu.run(prompt) -> str` method (§6.2), consistent with the other cookbook
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
execs only the single `# [fugu-core]` cell with `__name__` set to a non-`__main__`
value (so the live wiring block is skipped), and drives `Fugu` with **fake
agents**. A `FakeAgent` returns a canned `reply` whose `.content` is a fixed
string. Availability is controlled by setting/clearing provider env vars inside
each test.

### Unit Tests
- `Fugu.run` → `it('calls every available expert and synthesizes')` — happy path
- `Fugu.run` → `it('skips experts whose provider key is absent')` — [Hidden Assumption]
- `run` (ultra) → `it('runs the verifier pass when ultra=True and not when ultra=False')` — [Edge Case]
- `run` → `it('raises RuntimeError when no pool expert is available')` — [Silent Failure]
- `run` → `it('never calls an opted-out (excluded) expert')` — [Hidden Assumption]

### Integration Tests
- End-to-end (fakes): a pool of three vendors (`reasoning`(anthropic, key
  absent), `coding`(openai, key present), `long_context`(gemini, key absent)) —
  with only `OPENAI_API_KEY` set, assert only the OpenAI expert is called and
  the synthesizer is called once with a labeled output. This is the headline
  scenario the notebook's usage line is meant to exercise.
- Silent-failure path: when every provider key is cleared, `run` raises rather
  than the synthesizer being called with an empty list and returning a hollow
  answer.

### Manual / QA Test Cases
1. Given only `OPENAI_API_KEY`, running the cell calls only the OpenAI expert and
   prints one coherent final answer — [Hidden Assumption].
2. Given `exclude=("coding",)`, the coding expert is never called —
   [Hidden Assumption].
3. Given `ultra=True` vs `ultra=False` on the same prompt, the Ultra run performs
   an extra verifier call — [Edge Case].

---

## 11. Dependencies & External Services

| Dependency | Version / Endpoint | Purpose | Risk |
|------------|--------------------|---------|------|
| `vidbyte-sdk` | current repo surface | `BaseAgent` (default provider/model/middleware) | Pre-release API drift; mitigated by using only `BaseAgent(name, system_prompt)`. |
| OpenAI API | `OPENAI_API_KEY` | Default provider for synthesizer/verifier/pool | Cost; bounded by SDK-default middleware. |
| Anthropic/Gemini/xAI/DeepSeek APIs | respective keys (optional) | Multi-vendor pool; absent keys leave the expert unavailable | None when absent — absence is intended. |
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
- [x] **Class surface** → `run` + `orchestrate` only (confirmed by review
  feedback on PR #7).
- [x] **No routing plan / no tools / SDK-default config** → confirmed by review
  feedback on PR #8.
- [ ] **Pool vendor list.** Proposed: anthropic→reasoning, openai→coding,
  gemini→long_context, deepseek→fast. Illustrative only; only OpenAI runs in the
  default demo.

## 14. Alternatives Considered

### Alternative 1: `BaseAgent` with `ActorRuntime(dynamic_actors=True)`
- **What:** Use the SDK's built-in actor-model swarm — one agent that dynamically
  spawns sub-actors — as Fugu.
- **Why rejected:** It's the most literal "one agent orchestrating many," but it
  uses fixed personas on a single configured model and cannot express a
  *multi-vendor* swappable pool. Mentioned in the notebook's "what production
  adds / turn it up" section as the swarm upgrade path.

### Alternative 2: `ConditionalPipeline` + `MapReducePipeline` only
- **What:** Route with `ConditionalPipeline` (predicate) into a fixed
  `MapReducePipeline` (map to specialists, reduce to synthesis).
- **Why rejected:** `ConditionalPipeline`'s predicate is synchronous and keyword-
  based — it can't model a *learned* decision to assemble a team. `MapReducePipeline`
  is referenced in the narrative as the "static fixed-team" cousin of Fugu's
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

### Alternative 5: Keep the routing plan, subtask decomposition, tools, and explicit config
- **What:** The earlier `Fugu` with an `OrchestrationPlan` + orchestrator agent
  (`output_schema`), `Subtask`/`_resolve`/`_dispatch`/`_run_subtask`,
  `_solve_directly`, `_say`, recursive self-call, Wikipedia `search`/`read_article`
  tools, `provider`/`model`/`max_tool_rounds`/budget middleware configuration, and
  a `build_fugu()` factory.
- **Why rejected:** Review feedback on PR #7 and PR #8 asked to reduce the class
  to a "multi-agent orchestration" skeleton with only `orchestrate` and `run`,
  then further to remove the orchestration plan logic, the tools, and the
  provider/model/max_tool_rounds/budget configuration (SDK defaults). All of that
  machinery was removed and inlined into `orchestrate`.

---

END OF DESIGN DOC
