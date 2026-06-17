# Design Doc: Self-Refine — multi-agent refinement loop (Reflexion-style)

**Status:** Draft
**Author:** Claude
**Created:** 2026-06-17
**Last Updated:** 2026-06-17

---

## 1. Overview

A new SDK cookbook notebook, `sdk/self-refine/self_refine.ipynb`, that rebuilds the
**Reflexion / Self-Refine** pattern: a closed loop of three named agents that improve an
answer across iterations. A **planner** decomposes the task into typed subgoals; a
**worker** carries out the task (with whatever tools it is given) and emits a structured
**handoff** describing what it did; a **devil's-advocate debator** produces a typed list
of everything the worker got wrong. The critique is fed back to the planner *and* the
worker, and the cycle repeats until the debator can no longer find enough faults or a
hard iteration cap is hit. The notebook teaches both the architecture and the SDK
primitives that make it honest: `output_schema` for typed stage boundaries, the `handoff`
context primitive for cold-start continuation, and middleware budget guards for a loop
whose cost scales as `3 × iterations`.

---

## 2. Goals & Non-Goals

### Goals
- Add one self-contained, runnable notebook that rebuilds the multi-agent self-refinement
  loop using only `vidbyte-sdk`.
- Faithfully implement the user's specified data flow: plan → execute (+ handoff) →
  critique → re-plan, looping with two stopping conditions (`max_loop_iterations` and a
  `debator_items` fault threshold).
- Teach as it builds: every section explains *why* a primitive is load-bearing, and each
  major section ends with a specific reflection question for the reader.
- Use real SDK primitives — `output_schema` (Pydantic), `handoff=`/prebuilt handoffs,
  `AgentInput(context_items=...)`, budget/runtime middleware — not hand-rolled equivalents.
- Follow the cookbook's mandatory 7-section notebook structure and style rules.

### Non-Goals
- **No** unit tests or verification scripts (explicitly waived by the user for this task;
  Phases 5 and 5b of the design-doc workflow are skipped).
- **No** new code in the `vidbyte-sdk` package itself — the harness is composed entirely
  from existing public SDK surface inside the notebook.
- **No** filesystem persistence of plans/critiques — the run log is kept in memory.
- **No** parallelism (the loop is inherently sequential); no `SequentialPipeline` (it
  cannot carry typed objects or loop back — see §5).
- **No** accumulated multi-iteration reflection memory — only the *latest* critique is fed
  back. (Accumulation is documented as a "try next" extension.)

---

## 3. Background & Context

The cookbook's premise is "rebuild a well-known production agentic system, minimal and
from the ground up, in a single notebook." The three existing notebooks rebuild Factory's
Droid, OpenAI Deep Research, and Sierra. This notebook adds the canonical **self-improvement
loop** lineage — Reflexion (Shinn et al.) and Self-Refine (Madaan et al.) — decomposed into
three explicit agent roles.

The key Reflexion property the user's design preserves: the worker **re-attempts the task
from scratch each round**, carrying a *verbal* critique of its previous attempt — it does
**not** edit its prior artifact. This is what distinguishes it from a patch-in-place editor
and is why a separate critic agent (the debator) producing structured reflections is the
load-bearing piece.

Constraints discovered during the SDK audit that shape the design:
- **Pipelines are string-in/string-out** and explicitly carry no shared artifacts and no
  loop-back (`llms.txt`: "does not add shared context, budgets, artifacts… retries, or
  voting"). The loop therefore must be hand-orchestrated Python, not a built-in pipeline.
- **Handoff is a context primitive** (`Handoff` implements `ContextItem`), so it drops into
  the debator via `context_items=[doc]` with no string-stuffing.
- **Structured output makes termination deterministic** — a typed `Critique{items: [...]}`
  lets the stopping rule be `len(items) < debator_items`, far more robust than counting
  bullets in free text.
- **Auto-handoff is fail-open** — if handoff generation fails, the primary reply still
  returns and `agent.last_handoff` stays `None`; the loop must tolerate a missing handoff.

---

## 4. Requirements

### Functional Requirements
1. The notebook must run top-to-bottom on a clean Python 3.11+ environment with a single
   provider key in `.env`, installing its own dependencies in the first cell.
2. A **planner** agent must turn the task into a typed `Plan` (summary + ordered subgoals)
   via `output_schema`; the plan is saved into an in-memory run log each iteration.
3. On iteration 1 the planner receives only the original task. On iteration N≥2 it
   receives the original task **plus the latest critique** and produces a revised plan.
4. The **handoff shape** must be chosen by classifying the task once (before the loop) into
   one of the SDK prebuilts — `EngineeringHandoff`, `ResearchHandoff`, or `MinimalHandoff` —
   and reused every iteration.
5. A **worker** agent must execute the task using its configured tools, receiving the
   original task + the current plan + the latest critique checklist, and must emit a
   handoff document via the `handoff=` parameter (`reply.metadata["handoff"]`).
6. The worker must **not** receive its own previous output — each iteration is a fresh
   attempt informed only by the (revised) plan and the critique checklist.
7. A **debator** agent (devil's advocate) must receive the original task + the worker's
   output + the worker's handoff (via `context_items`) and produce a typed `Critique`
   whose `items` are individual faults; the notebook must render that list as bullets.
8. After each debator pass, the loop must stop when **either** the iteration count reaches
   `max_loop_iterations` **or** `len(critique.items) < debator_items` (strictly fewer).
9. The final returned answer is the **latest** iteration's worker output, alongside a
   `stop_reason` (`"converged"` or `"max_iterations"`) and the full per-iteration history.
10. Every agent must carry budget + runtime middleware; `max_loop_iterations` is the hard
    outer cap on total model calls.
11. Each major notebook section must end with a specific, content-anchored reflection
    question for the reader (teaching requirement).

### Non-Functional Requirements
- **Performance / cost:** cost scales as `~ (planner + worker + debator) × iterations`,
  plus a one-time classifier call. `CostBudgetMiddleware` and `RuntimeLimitMiddleware` cap
  each agent; `max_loop_iterations` (default 3) caps the loop.
- **Observability:** the in-memory run log records, per iteration, the plan, the worker
  output, the handoff, the critique, and the fault count, so the reader can watch the bug
  list shrink. `AuditLogMiddleware` is available as an optional observability guard.
- **Reliability / error tolerance:** structured-output extraction validates against the
  Pydantic schema and raises a clear error if validation fails; missing handoff is handled
  fail-open (debator still gets the worker's text).
- **Security:** keyless demo tools (Wikipedia public API); the worker is the only
  tool-using agent; planner and debator are reasoning-only.
- **Portability:** provider/model are env-driven; default OpenAI `gpt-4.1`, swappable to
  Anthropic `claude-opus-4-8` with no code change.

---

## 5. High-Level Design

The notebook builds four agents and one orchestrator class. Three agents are the named
roles from the user's design (planner, worker, debator); a small fourth **classifier**
implements "the agent decides the handoff shape" by mapping the task to a prebuilt handoff
spec once, before the loop.

The orchestrator is a hand-written Python class, **not** a `SequentialPipeline`. Pipelines
move only strings between stages and cannot loop; this loop must carry a typed `Plan`
object, a `Handoff` object, and a typed `Critique`, and must feed the critique backward to
the planner and worker. A class makes the data flow explicit and satisfies the cookbook's
class-first style.

Per-iteration data flow:

```
                ┌──────────────── critique (typed fault list) ────────────────┐
                │                                                              │
                ▼                                                              │
   ┌────────────────────┐   Plan         ┌──────────────────┐                 │ output + handoff
   │  PLANNER            │ ─────────────▶ │  WORKER           │                │
   │  output_schema=Plan │  + task        │  tools=<user>     │ ───────────────┴─────▶ ┌──────────────────────┐
   │  (re-plans from     │  + critique    │  handoff=<chosen> │                        │  DEBATOR              │
   │   critique on N≥2)  │                │  (fresh attempt)  │  context_items=[handoff]│  output_schema=       │
   └────────────────────┘                └──────────────────┘                        │  Critique             │
                ▲                                                                     └──────────────────────┘
                └───────────────────────── re-plan from critique ────────────────────────────┘

   handoff shape chosen ONCE up front:  CLASSIFIER (output_schema=HandoffChoice) → Engineering | Research | Minimal
   stop when:  iteration == max_loop_iterations   OR   len(critique.items) < debator_items
   final answer = latest worker output
```

Components created (all inside the one notebook):
- Pydantic schemas: `Subgoal`, `Plan`, `CritiqueItem`, `Critique`, `HandoffChoice`.
- Agents: `classifier`, `planner`, `worker` (forked per iteration), `debator`.
- Orchestrator: `SelfRefineLoop` (class) returning a `RefineResult` dataclass.
- Tools: keyless `search` / `read_article` over Wikipedia (the *worker's* swappable tools).

Key design decisions and why:
- **Class orchestrator over a pipeline** — typed artifacts + loop-back + backward critique
  cannot be expressed by `SequentialPipeline`.
- **Classify handoff once, reuse** — the task's nature doesn't change between iterations;
  re-classifying each round would add cost for no signal.
- **Fork the worker (and re-instantiate planner/debator) per iteration** — guarantees fresh
  message history each round, so the only thing carried forward is the explicit critique
  (the Reflexion property), not implicit conversation bleed.
- **Latest, not best, output returned** — per the user's decision; the design keeps full
  history so a reader can switch to best-by-fault-count in one line.

---

## 6. Detailed Design

### 6.1 Typed schemas (stage contracts)

**File:** `sdk/self-refine/self_refine.ipynb` (Section 3 cell)
**Type:** New

#### What it does
Defines the typed boundaries every agent speaks. Pydantic models are passed as
`output_schema`; the SDK returns the validated instance in `reply.metadata["structured"]`.

#### Interface / API
```python
class Subgoal(BaseModel):
    goal: str            # one concrete subgoal
    done_when: str       # acceptance criterion for this subgoal

class Plan(BaseModel):
    summary: str             # one-sentence restatement of the task
    subgoals: list[Subgoal]  # ordered, jointly sufficient subgoals

class CritiqueItem(BaseModel):
    issue: str       # specifically what the worker did wrong
    severity: str    # "high" | "medium" | "low"
    fix_hint: str    # what a corrected attempt should do instead

class Critique(BaseModel):
    items: list[CritiqueItem]  # one entry per distinct fault; [] means "no faults found"
    verdict: str               # one-line overall assessment

class HandoffChoice(BaseModel):
    kind: str    # "engineering" | "research" | "minimal"
    reason: str  # why this shape fits the task
```

#### Edge Cases & Error Handling
- A `get_structured(reply, schema)` helper raises a clear `RuntimeError` if
  `reply.metadata["structured"]` is missing (validation failed), surfacing the first 200
  chars of the raw reply for debugging.
- `Critique.items == []` is the convergence signal when `debator_items == 1`.

### 6.2 The four agents

**File:** `sdk/self-refine/self_refine.ipynb` (Section 5 cell)
**Type:** New

#### What it does
Constructs the classifier, planner, worker base, and debator with the right schema, tools,
middleware, and handoff configuration.

#### Interface / API
```python
classifier = BaseAgent(name="handoff-classifier", system_prompt=CLASSIFIER_PROMPT,
                       provider=PROVIDER, model_name=MODEL, output_schema=HandoffChoice)

planner    = BaseAgent(name="planner", system_prompt=PLANNER_PROMPT,
                       provider=PROVIDER, model_name=MODEL, output_schema=Plan)

worker_base = BaseAgent(name="worker", system_prompt=WORKER_PROMPT,
                        provider=PROVIDER, model_name=MODEL, tools=WORKER_TOOLS,
                        middleware=worker_middleware, max_tool_rounds=MAX_TOOL_ROUNDS,
                        handoff=<chosen prebuilt handoff>)   # set after classification

debator    = BaseAgent(name="debator", system_prompt=DEBATOR_PROMPT,
                       provider=PROVIDER, model_name=MODEL, output_schema=Critique)
```

#### Logic / Algorithm
1. Only the worker gets tools (the "whatever tools" passthrough). Planner, debator, and
   classifier are reasoning-only.
2. The chosen handoff prebuilt is set on the worker base via `handoff=`; forks inherit it.

#### Edge Cases & Error Handling
- If `reply.metadata.get("handoff")` is `None` (fail-open handoff failure), the loop falls
  back to `agent.last_handoff`, and if still `None`, the debator runs without a handoff
  context item (it still has the worker's output text).

### 6.3 `SelfRefineLoop` orchestrator

**File:** `sdk/self-refine/self_refine.ipynb` (Section 5 cell)
**Type:** New

#### What it does
Owns the loop: chooses the handoff shape once, then runs plan → execute → critique each
iteration, applies the two stopping rules, and records a per-iteration history.

#### Interface / API
```python
@dataclass
class RefineResult:
    final_output: str          # latest worker output
    final_plan: Plan           # latest plan
    stop_reason: str           # "converged" | "max_iterations"
    iterations_run: int
    history: list[dict]        # per-iteration: plan, output, handoff, critique, n_faults

class SelfRefineLoop:
    def __init__(self, task, *, planner, worker_base, debator, classifier,
                 max_loop_iterations=3, debator_items=1): ...
    def run(self) -> RefineResult: ...
    def _choose_handoff(self): ...                       # classifier → prebuilt handoff
    def _plan(self, critique) -> Plan: ...               # task (+critique on N≥2) → Plan
    def _execute(self, plan, critique): ...              # → (output_text, handoff_doc)
    def _critique(self, output, handoff_doc) -> Critique: ...
    def _should_stop(self, critique, iteration): ...     # → (bool, reason)
```

#### Logic / Algorithm
1. `_choose_handoff()` runs the classifier once; map `kind` → `EngineeringHandoff()` /
   `ResearchHandoff()` / `MinimalHandoff()`; rebuild the worker base with `handoff=spec`.
2. `critique = None`; `for i in 1..max_loop_iterations:`
   1. `plan = _plan(critique)` — fork a fresh planner; prompt includes the latest critique
      when `critique` is not `None`. Append to history.
   2. `output, handoff_doc = _execute(plan, critique)` — fork a fresh worker; prompt
      includes the plan and (when present) the critique checklist; read back
      `reply.metadata["handoff"]`.
   3. `critique = _critique(output, handoff_doc)` — fork a fresh debator; pass the handoff
      via `AgentInput(prompt, context_items=(handoff_doc,))` when present.
   4. `stop, reason = _should_stop(critique, i)`; if `stop`, return `RefineResult`.
3. If the loop exits via the cap, return with `stop_reason="max_iterations"`.

#### Edge Cases & Error Handling
- **Iteration 1 always runs fully** before the first stop check, so convergence can happen
  after one pass.
- `_should_stop` returns `("converged")` when `len(items) < debator_items`, else
  `("max_iterations")` only when `iteration == max_loop_iterations`.
- Missing handoff handled per §6.2.
- `debator_items` semantics documented inline: `=1` → stop only at zero faults; `=3` →
  stop at 0–2 faults.

### 6.4 Tools

**File:** `sdk/self-refine/self_refine.ipynb` (Section 3 cell)
**Type:** New

#### What it does
Two keyless `@tool` functions, `search` and `read_article`, over Wikipedia's public API —
the worker's swappable toolset for a grounded-explainer demo task.

#### Edge Cases & Error Handling
- `read_article` returns a clear "No article found" string for unknown titles; both tools
  set a `User-Agent` and a 30s timeout, and truncate extracts to keep token cost bounded.

---

## 7. Data Model Changes

N/A — no database or persisted schema. The only "models" are in-memory Pydantic stage
contracts (§6.1) and the in-memory `RefineResult`/history. No migration applies.

---

## 8. API Changes

N/A — this is a self-contained notebook. It adds no HTTP endpoints and changes no public
SDK API. It consumes existing public `vidbyte` imports only (`BaseAgent`, `AgentInput`,
`tool`, `Handoff` prebuilts, middleware).

---

## 9. File Change Manifest

| Action | File Path | Reason |
|--------|-----------|--------|
| CREATE | `docs/design/self-refine-harness.md` | This design doc (first commit on branch) |
| CREATE | `sdk/self-refine/self_refine.ipynb` | The new cookbook notebook |
| MODIFY | `README.md` | Add a row for `sdk/self-refine` to the Example Index table |
| MODIFY | `sdk/README.md` | Add a row for the notebook to the SDK examples table |

No tests or scripts are created (waived by the user for this task).

---

## 10. Testing Plan

Per the user's explicit instruction, **no automated tests or verification scripts are
created** for this notebook. Verification is by manual execution of the notebook itself.
The categories below are retained as the manual QA checklist rather than coded tests.

### Manual / QA Test Cases
1. Given a valid `.env` with one provider key, when the notebook is run top-to-bottom, then
   every cell executes without error and a final answer + `stop_reason` print. — [Edge Case]
2. Given a task the debator blesses immediately, when the loop runs, then it stops after
   iteration 1 with `stop_reason="converged"`. — [Edge Case]
3. Given a hard/subjective task with `debator_items=1`, when the loop runs, then it stops at
   `max_loop_iterations` with `stop_reason="max_iterations"` and still returns the latest
   output. — [Hidden Assumption: refinement is not guaranteed to converge]
4. Given a worker run whose auto-handoff fails, when the debator stage runs, then it still
   executes using the worker's text and the run does not abort. — [Hidden Failure]
5. Given a debator reply that fails schema validation, when `get_structured` runs, then a
   clear `RuntimeError` is raised rather than silently treating it as zero faults. — [Silent
   Failure: an unparsed critique must not be misread as convergence]
6. Given `debator_items=3`, when the debator returns exactly 3 faults, then the loop does
   **not** stop (strict `<`), and when it returns 2, it does. — [Silent Failure: off-by-one
   in the stop threshold]

---

## 11. Dependencies & External Services

| Dependency | Version / Endpoint | Purpose | Risk |
|------------|--------------------|---------|------|
| `vidbyte-sdk` | latest (pre-release) | Agents, handoff, middleware, structured output | API may shift pre-1.0 |
| `python-dotenv` | latest | Load `.env` provider keys | Low |
| `pydantic` | v2 | `output_schema` stage contracts | Low |
| `requests` | latest | Wikipedia tool HTTP calls | Network/availability |
| Wikipedia API | `en.wikipedia.org/w/api.php` | Keyless grounding corpus for the worker | Public endpoint rate limits |
| OpenAI/Anthropic | provider API | Model execution for all agents | Cost; requires key |

---

## 12. Rollout & Deployment

- No feature flags; no breaking changes (additive notebook + README rows).
- Deployment is a documentation/example PR to `main`; no service deploy.
- Rollback = revert the PR; nothing else depends on these files.

---

## 13. Open Questions

All four design forks were resolved with the user in the preceding `/talk` session:
- [x] Worker re-attempts fresh each round carrying only the latest critique (not editing
      its prior output).
- [x] Handoff shape classified once into a prebuilt.
- [x] Debator emits a structured fault list rendered as bullets; count drives termination.
- [x] Final answer = latest iteration's output.

Remaining minor confirmations (defaulted, easily changed in the notebook):
- [ ] Demo task = grounded Wikipedia explainer (keyless). Acceptable as the showcase task?
- [ ] Default constants: `max_loop_iterations=3`, `debator_items=1`. Reasonable defaults?

---

## 14. Alternatives Considered

### Alternative 1: `SequentialPipeline` (or a custom `BasePipeline`) for the loop
- What: express plan → execute → critique as an SDK pipeline.
- Why rejected: pipelines are string-only, carry no typed artifacts, and cannot loop or
  feed output backward. The loop needs a `Plan` object, a `Handoff` object, a typed
  `Critique`, and backward edges — a plain class is clearer and honest about the mechanics.

### Alternative 2: Worker refines its previous artifact in place
- What: feed the worker its prior output and have it patch it.
- Why rejected: the user chose the Reflexion behavior — fresh re-attempt carrying a verbal
  critique. It also avoids the worker getting anchored on a flawed first draft.

### Alternative 3: Free-text bulleted critique, parse line count
- What: let the debator write a markdown bullet list; count lines for the stop rule.
- Why rejected: brittle (markdown variance, sub-bullets, preamble lines). A typed
  `Critique.items` gives an exact, validated count and still renders as bullets for display.

### Alternative 4: Return the best (fewest-fault) iteration
- What: track and return the lowest-fault output.
- Why rejected: user chose "latest." History is retained so switching to best-by-count is a
  one-line change — documented as a "try next" extension.

---
