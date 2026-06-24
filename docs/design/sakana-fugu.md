# Design Doc: Sakana Fugu — multi-agent orchestration behind one model API

**Status:** Draft
**Author:** Claude
**Created:** 2026-06-22
**Last Updated:** 2026-06-22

---

## 1. Overview

Sakana Fugu is a product (announced 2026-06-22) that presents a *full multi-agent
orchestration system as a single model API*. You call one endpoint; internally a
learned orchestrator decides whether to answer directly or to assemble a team of
expert models drawn from a swappable, multi-vendor pool, then synthesizes their
work into one answer. Its headline differentiator is **resilience to
single-vendor disruption**: if a provider becomes unavailable (export controls,
outage, opt-out), Fugu dynamically routes the work to another model in the pool.
This feature adds a new cookbook example — `sdk/sakana-fugu/sakana_fugu.ipynb` —
that rebuilds that load-bearing architecture minimally with the Vidbyte SDK,
following the cookbook's existing "rebuild a production agentic system in one
notebook" format.

---

## 2. Goals & Non-Goals

### Goals
- Add one self-contained cookbook notebook that faithfully rebuilds Fugu's
  *load-bearing* architecture: single-model facade, learned route (direct vs.
  delegate), swappable multi-vendor pool, dispatch → synthesize, **route-around
  on provider unavailability**, two tiers (Fugu / Fugu Ultra), agent opt-out,
  and guarded recursive self-call.
- Use the minimal real `vidbyte-sdk` primitive set needed for the product shape:
  `BaseAgent`, `@tool`, `output_schema`, and budget/runtime/retry middleware.
- Keep the implementation minimal — the entire notebook is one executable code
  cell containing the Fugu facade and live SDK wiring — per the user's explicit
  "one Jupyter notebook cell, one code block" ask.
- Be runnable top-to-bottom with a single `OPENAI_API_KEY`, and make the
  route-around feature *demonstrable* with only that one key.
- Keep the folder as a single-notebook cookbook example and update both index READMEs.
- Ship a deterministic verification script that tests the orchestration logic
  (routing, route-around, opt-out, tiers, recursion) with fake agents — no live
  model calls.

### Non-Goals
- Training or imitating a real "orchestration model." Our orchestrator is a
  standard LLM prompted to emit a routing plan; we rebuild the *system
  architecture*, not Sakana's learned coordinator weights (Trinity/Conductor).
- An OpenAI-compatible HTTP server / endpoint. The "single API" is modeled as a
  single Python method (`Fugu.run`), matching the other cookbook notebooks.
- Benchmark reproduction, billing tiers, or subscription/pay-as-you-go logic.
- Streaming, persistent state, or a UI.
- Guaranteeing the named non-OpenAI providers actually run in the demo — they are
  intentionally treated as "unavailable" when their keys are absent, which is the
  whole point of the route-around demonstration.

---

## 3. Background & Context

- **Why now:** The product launched 2026-06-22 and is trending; the cookbook's
  premise is rebuilding well-known production agentic systems, so Fugu is a
  timely, on-format addition.
- **Problem it solves (for the reader):** Multi-agent orchestration is usually
  wired by hand and is brittle to single-vendor dependency. The notebook teaches
  both *what Fugu does* and *how little code the load-bearing skeleton takes* on
  the Vidbyte SDK.
- **Current state (base = `main`):** `sdk/` contains `droid/`, `deep-research/`,
  `sierra-support/`, and `self-refine/`, each one notebook; `docs/design/`
  already exists. `deep-research` and `self-refine` are the closest analogs —
  `deep-research` is a planner → researchers → synthesizer pipeline with
  `output_schema`; `self-refine` is a plain-Python class orchestrator
  (`SelfRefineLoop`) with small named methods and a `@dataclass` result. Fugu
  differs by adding *learned* routing, a *multi-vendor* pool, and *route-around*
  resilience, and follows `self-refine`'s class-orchestrator house style.
- **Constraints/dependencies:** The cookbook skill
  (`.claude/skills/vidbyte-cookbook-example.md`) mandates a self-contained
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
   request between `direct` (answer with one model) and `delegate` (decompose
   into subtasks assigned to pool specialties). Routing MUST come from the
   model's structured output, not a hardcoded keyword predicate.
3. The system MUST hold a **swappable, multi-vendor pool** of `BaseAgent`s keyed
   by specialty, each configured with a distinct `provider`/`model_name`. Adding
   or swapping a model MUST be a one-line change to the pool definition.
4. In `delegate` mode, the system MUST dispatch each subtask to its assigned pool
   model and then **synthesize** all worker outputs into one answer.
5. **Route-around (headline):** If a subtask's assigned model is unavailable —
   provider key absent, model opted out, or the call raises at runtime — Fugu
   MUST transparently route that subtask to another *available* pool model and
   still produce an answer. It MUST NEVER return an empty/partial answer silently
   because a provider was unavailable.
6. If *no* pool model is available, `Fugu.run` MUST raise a clear, explicit error
   (not return `""` or a misleading success).
7. **Opt-out:** The caller MUST be able to exclude specific pool members (by key)
   for privacy/compliance; excluded members MUST be treated as unavailable for
   both assignment and route-around.
8. **Two tiers:** `Fugu` (fast: synthesize once, no verification) and
   `Fugu Ultra` (`ultra=True`: add a verification/critique pass over the
   synthesized answer). Both MUST be the same class behind the same `run` API.
9. **Recursive self-call:** The orchestrator MAY assign a subtask to Fugu itself;
   recursion MUST be depth-limited so it always terminates.
10. `delegate` mode with an empty subtask list MUST fall back to `direct` rather
    than returning an empty answer.
11. An unknown `assigned_to` key MUST route around (pick any available model),
    not raise `KeyError`.
12. The notebook MUST expose a one-line `build_fugu().run(...)` usage path that
    demonstrates route-around with only `OPENAI_API_KEY` set.

### Non-Functional Requirements
- **Minimalism:** One notebook cell; prefer SDK built-ins over custom code.
- **Cost/latency control:** Every SDK agent (orchestrator, pool members,
  synthesizer, verifier) MUST run under budget + runtime middleware so one
  request cannot run away. Provider-resilience middleware (`ModelRetryMiddleware`)
  MUST be attached to make the route-around narrative concrete at the SDK layer.
- **Observability:** A `verbose` switch MUST print the routing decision and each
  dispatch/route-around event so the reader can see orchestration happening.
- **Testability:** The orchestration core MUST be exercisable with fake,
  duck-typed agents and no network/model/SDK dependency, so the Phase 5 script is
  deterministic and offline.
- **Honesty:** The notebook MUST clearly state what is real (architecture) vs.
  stubbed (the "learned coordinator" is just a prompted LLM; non-OpenAI vendors
  are availability-gated), per cookbook norms.

---

## 5. High-Level Design

The notebook builds a single `Fugu` facade class over three kinds of SDK
`BaseAgent`s plus a model pool:

- **Orchestrator** — *the "Fugu model."* A `BaseAgent` with
  `output_schema=OrchestrationPlan`. Given a prompt it returns a typed plan:
  `mode` (`direct`/`delegate`), `reasoning`, and (when delegating) a list of
  `Subtask`s each with an `assigned_to` specialty key.
- **Pool** — a list of `PoolModel` records (`key`, `provider`, `model`, `agent`),
  each a `BaseAgent` on a distinct vendor (`anthropic` reasoning, `openai`
  coding/fast, `gemini` long-context, `deepseek`/`xai` …). "The world's best
  models," entirely swappable by editing the list. Pool members carry the proven
  keyless Wikipedia `search`/`read_article` tools so delegated subtasks produce
  grounded output.
- **Synthesizer** — a `BaseAgent` that merges worker outputs into one answer.
- **Verifier** (Ultra only) — a `BaseAgent` that critiques and finalizes the
  synthesized answer.

`Fugu.run` orchestrates internally and returns one string:

```
                         +--------------------------- Fugu.run(prompt) ---------------------------+
                         |                                                                        |
  prompt --> ORCHESTRATOR|  plan.mode == "direct"   -->  one available model  -------------> answer
   (one     (output_schema|                                                                       |
    API)     = Plan)      |  plan.mode == "delegate" --> for each subtask:                          |
                         |        resolve(assigned_to) --[unavailable? route around]--> pool model |
                         |        (assigned_to == "fugu" & depth<MAX --> recurse self)              |
                         |        gather worker outputs --> SYNTHESIZER --> draft                   |
                         |        if ultra: --> VERIFIER --> final                                  |
                         +------------------------------------------------------------------------+
                 pool = [anthropic:reasoning, openai:coding, gemini:long_context, deepseek:fast, ...]
                 availability = (key not opted out) AND (provider API key present)
```

**Key design decisions:**
- **Learned routing via `output_schema`, not `ConditionalPipeline`.** Fugu's
  routing is a model decision over open-ended assignments; `ConditionalPipeline`'s
  predicate is synchronous/keyword-based and can't express "the model decomposes
  and assigns." We drive a dynamic dispatch from the orchestrator's structured
  plan. (`MapReducePipeline` is the closest static analog and is named in the
  narrative as the "fixed-team" version.)
- **Class orchestrator, not a pipeline** — matches the `self-refine` house style:
  typed objects and a conditional/recursive control flow cross stage boundaries,
  which pipelines (string-in/string-out) can't carry.
- **Availability gating is the demo.** With only `OPENAI_API_KEY`, the
  anthropic/gemini/xai subtasks are "unavailable" and Fugu routes them to the
  OpenAI model — making the headline feature runnable with one key and one
  visible printout.
- **Availability is a plain env-var lookup** (`PROVIDER_ENV` dict) inside the
  core class, so the core has *zero* SDK import at definition time and the test
  harness can exec it offline. The narrative points to
  `ProviderModelRegistry.get_api_key_env_var` as the SDK-native equivalent.
- **Tiers are one flag** (`ultra`) on one class — matching "both models, one API."
- **Duck-typed pool agents.** `Fugu` only calls `.run(str).content` on pool
  members, so tests inject fakes.

---

## 6. Detailed Design

The deliverable is one notebook with exactly one executable code cell. That cell
is marked with a leading `# [fugu-core]` sentinel comment so the verification
script can exec it offline. Top-level definitions import only `os`,
`dataclasses`, `typing`, and `pydantic`; live SDK imports happen inside
`build_fugu()`, so tests can exercise `Fugu` with fakes without importing
`vidbyte` or making model calls.

### 6.1 Schemas (`# [fugu-core]`)

**File(s):** `sdk/sakana-fugu/sakana_fugu.ipynb`
**Type:** New

#### What it does
Typed boundary for the orchestrator's routing decision.

#### Interface / API
```python
from __future__ import annotations
from pydantic import BaseModel, Field

class Subtask(BaseModel):
    description: str = Field(description="A self-contained unit of work.")
    assigned_to: str = Field(description="Pool specialty key best suited to this subtask, e.g. 'reasoning'.")

class OrchestrationPlan(BaseModel):
    mode: str = Field(description='Exactly "direct" (one model) or "delegate" (assemble a team).')
    reasoning: str = Field(description="One sentence: why this route.")
    subtasks: list[Subtask] = Field(default_factory=list, description="Subtasks when delegating; empty when direct.")
```
`mode` is a value-constrained `str` (not `Literal`) to match the proven house
structured-output pattern.

#### Edge Cases & Error Handling
- `mode="delegate"` with empty `subtasks` → handled by `Fugu` (falls back to direct).
- Provider that doesn't support / fails structured output → `_orchestrate` reads
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
The single-model facade. Orchestrates internally; returns one answer. Class-first
with small, plain-English methods composed by `run`.

#### Interface / API
```python
PROVIDER_ENV = {
    "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY", "xai": "XAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
}
MAX_RECURSION_DEPTH = 2

class Fugu:
    def __init__(self, orchestrator, pool, synthesizer, verifier=None, *, ultra=False, exclude=(), verbose=False): ...
    def run(self, prompt: str, _depth: int = 0) -> str: ...        # public single-model API
    # private, semantically named:
    def _orchestrate(self, prompt: str) -> OrchestrationPlan: ...  # ask the Fugu model how to route (safe-fallback to direct)
    def _available(self, key: str) -> bool: ...                    # member not opted out and provider key present
    def _resolve(self, requested_key: str) -> PoolModel: ...       # assigned model, or route around to any available
    def _run_subtask(self, task: Subtask, depth: int) -> str: ...  # dispatch one subtask (recurse if assigned to 'fugu')
    def _dispatch(self, subtasks, depth: int) -> list[str]: ...    # run every subtask, collecting source-labeled outputs
    def _synthesize(self, prompt: str, outputs: list[str]) -> str: ...
    def _verify(self, prompt: str, answer: str) -> str: ...        # Ultra-only critique/finalize pass
    def _solve_directly(self, prompt: str) -> str: ...             # answer with a single available model
    def _say(self, msg: str) -> None: ...                          # verbose trace
```

#### Logic / Algorithm
`run(prompt, _depth=0)`:
1. `plan = self._orchestrate(prompt)`; print decision if verbose.
2. If `plan.mode != "delegate"` **or** `not plan.subtasks` → `return self._solve_directly(prompt)`.
3. `outputs = self._dispatch(plan.subtasks, _depth)`.
4. `answer = self._synthesize(prompt, outputs)`.
5. `return self._verify(prompt, answer) if (self.ultra and self.verifier) else answer`.

`_orchestrate`: call `self.orchestrator.run(prompt)`; read
`reply.metadata.get("structured")`; coerce to `OrchestrationPlan`
(`model_validate` if a dict); on missing/invalid, return
`OrchestrationPlan(mode="direct", reasoning="fallback: no structured plan")`.

`_available(key)`: `key in self.by_key` AND `key not in self.exclude` AND
`os.getenv(PROVIDER_ENV.get(self.by_key[key].provider, "")) ` truthy. Unknown key → `False`.

`_resolve(requested_key)`:
1. If `_available(requested_key)` → return `self.by_key[requested_key]`.
2. Else iterate pool in declared order; return the first `_available` member
   (route-around; print a notice if verbose).
3. If none available → raise `RuntimeError("Fugu: no available models in pool")`.

`_run_subtask(task, depth)`:
1. If `task.assigned_to == "fugu"` and `depth < MAX_RECURSION_DEPTH` → return
   `self.run(task.description, _depth=depth+1)` (recursive self-call).
2. `member = self._resolve(task.assigned_to)`.
3. `try: return f"[{member.key}] " + member.agent.run(task.description).content`
   `except Exception:` route around among the *remaining* available members
   (exclude the failed key); run a substitute if one exists; otherwise re-raise.

`_dispatch(subtasks, depth)`: `return [self._run_subtask(t, depth) for t in subtasks]`.

`_synthesize`: `self.synthesizer.run(prompt + "\n\nExpert outputs:\n" + "\n\n".join(outputs)).content`.

`_verify`: `self.verifier.run(<prompt + draft answer>).content`.

`_solve_directly`: `self._resolve("__any__").agent.run(prompt).content` (the
`"__any__"` sentinel is never a real key, so `_resolve` falls through to "first
available," reusing the route-around path).

#### Edge Cases & Error Handling
- Empty pool / all opted out / no keys → `_resolve` raises `RuntimeError` (Req 6).
- `delegate` + empty subtasks → step 2 falls back to direct (Req 10).
- Unknown `assigned_to` → `_resolve` route-around path (Req 11).
- Runtime call failure → in-call route-around to a remaining available member
  (Req 5); only re-raises if no substitute remains.
- Recursion → capped at `MAX_RECURSION_DEPTH` (Req 9); beyond the cap, `"fugu"`
  assignments resolve as ordinary route-around to a model.
- Structured-output failure → safe `direct` fallback, never a crash.

### 6.4 System prompts

**File(s):** same notebook
**Type:** New

Three compact prompt strings in the same cell: ORCHESTRATOR (routing policy +
the list of specialty keys incl. `fugu`; prefer `direct` for simple asks,
`delegate` for hard/multi-domain ones), SYNTHESIZER (merge expert outputs into
one authoritative answer, reconcile conflicts), VERIFIER (Ultra: check the
answer against the request, fix errors, return the final answer only).

### 6.5 Pool, agents, tools & middleware construction

**File(s):** same notebook, same `# [fugu-core]` cell.
**Type:** New

`build_fugu()` imports the minimal SDK surface, defines the keyless Wikipedia
tools (`search`, `read_article`), builds the orchestrator/synthesizer/verifier
`BaseAgent`s, and returns a configured `Fugu`. Middleware (verified signatures)
attached to each agent:
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

N/A — no database, schema, or persistent store. The only "schemas" are the
in-notebook Pydantic models (`Subtask`, `OrchestrationPlan`) defined in §6.1,
used purely as the orchestrator's structured-output boundary.

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
execs only the single `# [fugu-core]` cell (offline, no SDK), and drives `Fugu` with
**fake agents**. A `FakeAgent` returns a canned `reply` whose `.content` is a
fixed string and (for the orchestrator) whose `.metadata["structured"]` is a
chosen `OrchestrationPlan`. A `FailingAgent` raises on `.run`. Availability is
controlled by setting/clearing provider env vars inside each test.

### Unit Tests
- `Fugu.run` → `it('returns a single string in direct mode without dispatching')` — [Edge Case]
- `Fugu.run` → `it('dispatches each subtask and synthesizes in delegate mode')` — happy path
- `_resolve` → `it('returns the assigned model when its provider key is present')` — happy path
- `_resolve` → `it('routes around to an available model when the assigned provider key is absent')` — [Hidden Assumption]
- `_resolve` → `it('routes around for an unknown assigned_to key instead of raising KeyError')` — [Hidden Failure]
- `_resolve` → `it('treats an opted-out (excluded) member as unavailable even if its key is present')` — [Hidden Assumption]
- `_resolve` → `it('raises RuntimeError when no pool model is available')` — [Silent Failure]
- `run` → `it('falls back to direct when mode is delegate but subtasks is empty')` — [Silent Failure]
- `run` → `it('handles a delegate plan with exactly one subtask (N=1)')` — [Edge Case]
- `_run_subtask` → `it('routes around at runtime when the assigned agent.run raises mid-call')` — [Hidden Failure]
- `_run_subtask` → `it('re-raises only when no substitute remains after a runtime failure')` — [Hidden Failure]
- `_run_subtask` → `it('recurses into Fugu when assigned_to == "fugu" and stops at MAX_RECURSION_DEPTH')` — [Hidden Failure]
- `run` (ultra) → `it('runs the verifier pass when ultra=True and not when ultra=False')` — [Edge Case]
- `_orchestrate` → `it('falls back to a direct plan when structured output is missing/invalid')` — [Silent Failure]
- `_dispatch` → `it('labels each output with its source model key')` — [Silent Failure]

### Integration Tests
- End-to-end (fakes): a `delegate` plan with three subtasks assigned to
  `reasoning`(anthropic, key absent), `coding`(openai, key present),
  `long_context`(gemini, key absent) — with only `OPENAI_API_KEY` set, assert all
  three resolve to the OpenAI member (route-around) and the synthesizer is called
  once with three labeled outputs. This is the headline-feature path and the
  exact scenario the notebook's usage line is meant to exercise.
- Silent-failure path: when the orchestrator emits `delegate` but every provider
  key is cleared, `run` raises rather than the synthesizer being called with an
  empty list and returning a hollow answer.
- Hidden assumption: the orchestrator may assign a key not in the pool; assert the
  dispatch still completes via route-around through a real `OrchestrationPlan`
  `model_validate` round-trip.

### Manual / QA Test Cases
1. Given only `OPENAI_API_KEY`, running `build_fugu().run(...)` with
   `verbose=True` shows non-OpenAI subtasks re-routed to the OpenAI model and a
   single coherent final answer — [Hidden Assumption].
2. Given `ANTHROPIC_API_KEY` also set, `reasoning` subtasks resolve to the
   anthropic member (no route-around for that key) — [Edge Case].
3. Given `exclude=("coding",)`, a subtask assigned to `coding` routes around —
   [Hidden Assumption].
4. Given a simple factual prompt, `mode` is `direct` and only one model is
   consulted (verbose shows no dispatch) — [Edge Case].
5. Given `ultra=True` vs `ultra=False` on the same delegate prompt, the Ultra run
   performs an extra verifier call visible in verbose output — [Edge Case].

---

## 11. Dependencies & External Services

| Dependency | Version / Endpoint | Purpose | Risk |
|------------|--------------------|---------|------|
| `vidbyte-sdk` | current repo surface | `BaseAgent`, `output_schema`, `fork`, middleware | Pre-release API drift; mitigated by using only documented/verified primitives. |
| `pydantic` | 2.x | Structured-output schemas | Low; used by sibling notebooks. |
| `python-dotenv` | any | Load `.env` | Low. |
| `requests` | any | Keyless Wikipedia tools for pool members | Low; reused verbatim from siblings. |
| OpenAI API | `OPENAI_API_KEY` | Default provider for orchestrator/synthesizer/pool | Cost; mitigated by budget/runtime middleware. |
| Anthropic/Gemini/xAI/DeepSeek APIs | respective keys (optional) | Real multi-vendor pool; absent keys drive the route-around demo | None when absent — absence is intended. |
| stdlib `json` | — | Test harness reads the notebook (no nbformat dep) | Low; JSON parse only. |

---

## 12. Rollout & Deployment

- **Feature flags:** None.
- **Breaking change:** No — purely additive (one new folder + README rows).
- **Deployment order:** N/A (documentation/example repo).
- **Rollback:** Revert the branch / delete `sdk/sakana-fugu/` and the README rows.
- **Process:** Worktree branch `feat/sakana-fugu-cookbook-example` off `origin/main`;
  design-doc commit first, then notebook, then test script, then README updates;
  open a **draft PR targeting `main`** with this doc as the body.

---

## 13. Open Questions

- [x] **Folder name** → `sdk/sakana-fugu/` (confirmed; named after the rebuilt system).
- [x] **Base branch** → branch off `origin/main`, PR into `main` (confirmed;
  `main` already contains the cookbook content — local `main` was merely stale).
- [ ] **Pool vendor list / model ids.** Proposed: anthropic→reasoning,
  openai→coding, gemini→long_context, deepseek→fast. Illustrative only; only
  OpenAI runs in the default demo. Confirm exact model ids to name.
- [ ] **Recursive self-call depth.** `MAX_RECURSION_DEPTH = 2` proposed.

## 14. Alternatives Considered

### Alternative 1: `BaseAgent` with `ActorRuntime(dynamic_actors=True)`
- **What:** Use the SDK's built-in actor-model swarm — one agent that dynamically
  spawns sub-actors — as Fugu.
- **Why rejected:** It's the most literal "one agent orchestrating many," but it
  is *strictly incompatible with middleware* (the cookbook format requires budget
  + safety middleware) and uses fixed personas on a single configured model. It
  cannot express Fugu's defining features: a *multi-vendor* swappable pool and
  *route-around on provider unavailability*. Mentioned in the notebook's "what
  production adds / turn it up" section as the swarm upgrade path.

### Alternative 2: `ConditionalPipeline` + `MapReducePipeline` only
- **What:** Route with `ConditionalPipeline` (predicate) into a fixed
  `MapReducePipeline` (map to specialists, reduce to synthesis).
- **Why rejected:** `ConditionalPipeline`'s predicate is synchronous and keyword-
  based — it can't model a *learned* decomposition with per-subtask model
  assignment, and `MapReducePipeline` has a *fixed* map set, so it can't route
  around an unavailable member. We instead drive dynamic dispatch from the
  orchestrator's `output_schema` plan. `MapReducePipeline` is referenced in the
  narrative as the "static fixed-team" cousin of Fugu's dynamic dispatch.

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

---

END OF DESIGN DOC
