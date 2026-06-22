"""Deterministic, offline verification of the Sakana Fugu orchestration core.

Loads sdk/sakana-fugu/sakana_fugu.ipynb, execs ONLY the cells marked
`# [fugu-core]` (which import just the stdlib + pydantic, no vidbyte), and drives
the `Fugu` class with fake duck-typed agents. No network, no model, no API key.

Run:  python scripts/test_sakana_fugu.py
Exits non-zero if any test fails.
"""
import json
import os
import sys
import traceback
from pathlib import Path

# --------------------------------------------------------------------------- #
# Load the orchestration core out of the notebook (only the `# [fugu-core]` cells)
# --------------------------------------------------------------------------- #
NB_PATH = Path(__file__).resolve().parent.parent / "sdk" / "sakana-fugu" / "sakana_fugu.ipynb"


def load_core_namespace(nb_path: Path) -> dict:
    """Exec every `# [fugu-core]` code cell from the notebook into a fresh namespace and return it."""
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    ns: dict = {}
    found = 0
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        src = cell["source"]
        src = "".join(src) if isinstance(src, list) else src
        if src.lstrip().startswith("# [fugu-core]"):
            # dont_inherit=True: compile the cell exactly as written, never inheriting
            # this harness's own __future__ flags (which would break Pydantic forward refs).
            exec(compile(src, "<fugu-core>", "exec", dont_inherit=True), ns)
            found += 1
    if found == 0:
        raise RuntimeError("No `# [fugu-core]` cells found in the notebook.")
    return ns


CORE = load_core_namespace(NB_PATH)
Fugu = CORE["Fugu"]
OrchestrationPlan = CORE["OrchestrationPlan"]
Subtask = CORE["Subtask"]
PoolModel = CORE["PoolModel"]
PROVIDER_ENV = CORE["PROVIDER_ENV"]
MAX_RECURSION_DEPTH = CORE["MAX_RECURSION_DEPTH"]


# --------------------------------------------------------------------------- #
# Fakes — duck-typed agents (anything with .run(str) -> reply.content)
# --------------------------------------------------------------------------- #
class Reply:
    def __init__(self, content="", structured=None):
        self.content = content
        self.metadata = {} if structured is None else {"structured": structured}


class FakeAgent:
    """Records calls and returns a fixed content string."""
    def __init__(self, content="ok"):
        self.content = content
        self.calls = 0
        self.prompts: list[str] = []

    def run(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        return Reply(self.content)


class OrchestratorFake:
    """Returns a fixed structured OrchestrationPlan every call."""
    def __init__(self, plan):
        self.plan = plan
        self.calls = 0

    def run(self, prompt):
        self.calls += 1
        return Reply("", structured=self.plan)


class NoStructuredOrchestrator:
    """Returns free text with no structured payload (forces the safe fallback)."""
    def __init__(self):
        self.calls = 0

    def run(self, prompt):
        self.calls += 1
        return Reply("free text, no structured plan")


class FailingAgent:
    """Raises at runtime to exercise in-call route-around."""
    def __init__(self):
        self.calls = 0

    def run(self, prompt):
        self.calls += 1
        raise RuntimeError("provider down")


def pm(key, provider, agent):
    return PoolModel(key=key, provider=provider, model="m", agent=agent)


def set_providers(*providers):
    """Make exactly these providers 'available' by setting their key env vars; clear the rest."""
    for env_var in PROVIDER_ENV.values():
        os.environ.pop(env_var, None)
    for p in providers:
        os.environ[PROVIDER_ENV[p]] = "test-key"


def plan_direct():
    return OrchestrationPlan(mode="direct", reasoning="simple")


def plan_delegate(*assignees):
    return OrchestrationPlan(
        mode="delegate", reasoning="hard",
        subtasks=[Subtask(description=f"do {a}", assigned_to=a) for a in assignees],
    )


# --------------------------------------------------------------------------- #
# Tests  (name, fn)  — fn raises AssertionError on failure
# --------------------------------------------------------------------------- #
def t_direct_single_no_dispatch():
    set_providers("openai")
    synth, member = FakeAgent("SYNTH"), FakeAgent("DIRECT-ANSWER")
    f = Fugu(OrchestratorFake(plan_direct()), [pm("coding", "openai", member)], synth)
    out = f.run("hi")
    assert out == "DIRECT-ANSWER", out
    assert synth.calls == 0, "synthesizer must not run in direct mode"
    assert member.calls == 1


def t_delegate_dispatch_and_synthesize():
    set_providers("openai")
    e, synth = FakeAgent("E"), FakeAgent("FINAL")
    f = Fugu(OrchestratorFake(plan_delegate("coding", "coding")), [pm("coding", "openai", e)], synth)
    out = f.run("hard")
    assert out == "FINAL", out
    assert e.calls == 2, "each subtask must be dispatched"
    assert synth.calls == 1
    assert "[coding] E" in synth.prompts[0], "synth must receive labeled expert outputs"


def t_resolve_assigned_when_key_present():
    set_providers("openai", "anthropic")
    a, c = FakeAgent("A"), FakeAgent("C")
    f = Fugu(OrchestratorFake(plan_direct()), [pm("reasoning", "anthropic", a), pm("coding", "openai", c)], FakeAgent())
    assert f._resolve("reasoning").key == "reasoning"


def t_route_around_when_key_absent():
    set_providers("openai")  # anthropic absent
    a, c = FakeAgent("A"), FakeAgent("C")
    f = Fugu(OrchestratorFake(plan_direct()), [pm("reasoning", "anthropic", a), pm("coding", "openai", c)], FakeAgent())
    assert f._resolve("reasoning").key == "coding", "must route around the unavailable assigned model"


def t_route_around_unknown_key_no_keyerror():
    set_providers("openai")
    c = FakeAgent("C")
    f = Fugu(OrchestratorFake(plan_direct()), [pm("coding", "openai", c)], FakeAgent())
    assert f._resolve("nonexistent-specialty").key == "coding"


def t_excluded_member_unavailable():
    set_providers("openai", "anthropic")
    a, c = FakeAgent("A"), FakeAgent("C")
    f = Fugu(OrchestratorFake(plan_direct()),
             [pm("reasoning", "anthropic", a), pm("coding", "openai", c)], FakeAgent(), exclude={"reasoning"})
    assert f._available("reasoning") is False, "opted-out member must be unavailable even with its key present"
    assert f._resolve("reasoning").key == "coding"


def t_no_available_raises():
    set_providers()  # clear all
    f = Fugu(OrchestratorFake(plan_direct()), [pm("coding", "openai", FakeAgent())], FakeAgent())
    try:
        f._resolve("coding")
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError when no model is available")


def t_delegate_empty_subtasks_falls_back_to_direct():
    set_providers("openai")
    member, synth = FakeAgent("DIRECT"), FakeAgent("SYNTH")
    plan = OrchestrationPlan(mode="delegate", reasoning="x", subtasks=[])
    out = Fugu(OrchestratorFake(plan), [pm("coding", "openai", member)], synth).run("x")
    assert out == "DIRECT", out
    assert synth.calls == 0, "empty delegate must not produce a hollow synthesized answer"


def t_single_subtask_n_equals_1():
    set_providers("openai")
    e, synth = FakeAgent("E"), FakeAgent("FINAL")
    f = Fugu(OrchestratorFake(plan_delegate("coding")), [pm("coding", "openai", e)], synth)
    assert f.run("x") == "FINAL"
    assert e.calls == 1 and synth.calls == 1


def t_runtime_route_around_on_raise():
    set_providers("openai", "anthropic")
    failing, good = FailingAgent(), FakeAgent("GOOD")
    f = Fugu(OrchestratorFake(plan_delegate("reasoning")),
             [pm("reasoning", "anthropic", failing), pm("coding", "openai", good)], FakeAgent("FINAL"))
    out = f.run("x")
    assert failing.calls == 1, "assigned model must be attempted"
    assert good.calls == 1, "must route around to a working model after a runtime failure"
    assert out == "FINAL"


def t_reraise_when_no_substitute_remains():
    set_providers("anthropic")  # only the failing model is available
    failing = FailingAgent()
    f = Fugu(OrchestratorFake(plan_delegate("reasoning")), [pm("reasoning", "anthropic", failing)], FakeAgent("FINAL"))
    try:
        f.run("x")
    except RuntimeError:
        assert failing.calls == 1
        return
    raise AssertionError("expected RuntimeError when a failed model has no substitute")


def t_recursion_depth_capped():
    set_providers("openai")
    member, synth = FakeAgent("LEAF"), FakeAgent("SYNTH")
    orc = OrchestratorFake(plan_delegate("fugu"))  # always delegates one recursive subtask
    out = Fugu(orc, [pm("coding", "openai", member)], synth).run("x")
    assert orc.calls == MAX_RECURSION_DEPTH + 1, f"recursion must stop at the depth cap (got {orc.calls})"
    assert isinstance(out, str)
    assert member.calls == 1, "the deepest level resolves to a real model exactly once"


def t_ultra_runs_verifier_else_not():
    set_providers("openai")
    base = Fugu(OrchestratorFake(plan_delegate("coding")), [pm("coding", "openai", FakeAgent("E"))], FakeAgent("DRAFT"))
    assert base.run("x") == "DRAFT", "base tier must not verify"
    ver = FakeAgent("VERIFIED")
    ultra = Fugu(OrchestratorFake(plan_delegate("coding")), [pm("coding", "openai", FakeAgent("E"))],
                 FakeAgent("DRAFT"), verifier=ver, ultra=True)
    assert ultra.run("x") == "VERIFIED"
    assert ver.calls == 1


def t_orchestrate_fallback_on_missing_structured():
    set_providers("openai")
    member, synth = FakeAgent("DIRECT"), FakeAgent("SYNTH")
    out = Fugu(NoStructuredOrchestrator(), [pm("coding", "openai", member)], synth).run("x")
    assert out == "DIRECT", "missing structured output must fall back to direct"
    assert synth.calls == 0


def t_dispatch_labels_outputs():
    set_providers("openai")
    e = FakeAgent("HELLO")
    f = Fugu(OrchestratorFake(plan_delegate("coding")), [pm("coding", "openai", e)], FakeAgent())
    outs = f._dispatch([Subtask(description="d", assigned_to="coding")], 0)
    assert outs == ["[coding] HELLO"], outs


# ---- integration ---------------------------------------------------------- #
def t_integration_route_around_three_vendors_one_key():
    set_providers("openai")  # the headline scenario: only OpenAI present
    r, c, l, synth = FakeAgent("R"), FakeAgent("C"), FakeAgent("L"), FakeAgent("FINAL")
    pool = [pm("reasoning", "anthropic", r), pm("coding", "openai", c), pm("long_context", "gemini", l)]
    f = Fugu(OrchestratorFake(plan_delegate("reasoning", "coding", "long_context")), pool, synth)
    out = f.run("x")
    assert c.calls == 3, "all three subtasks must resolve to the only available (OpenAI) model"
    assert r.calls == 0 and l.calls == 0, "unavailable vendors must not be called"
    assert synth.calls == 1 and out == "FINAL"


def t_integration_delegate_all_dark_raises():
    set_providers()  # every provider unavailable
    synth = FakeAgent("FINAL")
    f = Fugu(OrchestratorFake(plan_delegate("reasoning")), [pm("reasoning", "anthropic", FakeAgent("R"))], synth)
    try:
        f.run("x")
    except RuntimeError:
        assert synth.calls == 0, "must not synthesize a hollow answer when the pool is dark"
        return
    raise AssertionError("expected RuntimeError when delegating with no available model")


def t_integration_unknown_key_via_model_validate():
    set_providers("openai")
    c, synth = FakeAgent("C"), FakeAgent("FINAL")
    raw = {"mode": "delegate", "reasoning": "r",
           "subtasks": [{"description": "d", "assigned_to": "quantum_oracle"}]}
    plan = OrchestrationPlan.model_validate(raw)  # real round-trip, as the SDK would produce
    f = Fugu(OrchestratorFake(plan), [pm("coding", "openai", c)], synth)
    out = f.run("x")
    assert c.calls == 1, "an orchestrator-assigned key absent from the pool must route around"
    assert out == "FINAL"


TESTS = [
    ("direct mode returns one string, no dispatch [Edge Case]", t_direct_single_no_dispatch),
    ("delegate dispatches each subtask and synthesizes [happy]", t_delegate_dispatch_and_synthesize),
    ("_resolve returns assigned model when key present [happy]", t_resolve_assigned_when_key_present),
    ("_resolve routes around when assigned key absent [Hidden Assumption]", t_route_around_when_key_absent),
    ("_resolve routes around unknown key, no KeyError [Hidden Failure]", t_route_around_unknown_key_no_keyerror),
    ("excluded member treated as unavailable [Hidden Assumption]", t_excluded_member_unavailable),
    ("_resolve raises when no model available [Silent Failure]", t_no_available_raises),
    ("delegate w/ empty subtasks falls back to direct [Silent Failure]", t_delegate_empty_subtasks_falls_back_to_direct),
    ("delegate with exactly one subtask (N=1) [Edge Case]", t_single_subtask_n_equals_1),
    ("runtime route-around when agent.run raises [Hidden Failure]", t_runtime_route_around_on_raise),
    ("re-raise only when no substitute remains [Hidden Failure]", t_reraise_when_no_substitute_remains),
    ("recursive self-call capped at MAX_RECURSION_DEPTH [Hidden Failure]", t_recursion_depth_capped),
    ("ultra runs verifier; base tier does not [Edge Case]", t_ultra_runs_verifier_else_not),
    ("_orchestrate falls back to direct on missing structured [Silent Failure]", t_orchestrate_fallback_on_missing_structured),
    ("_dispatch labels each output with its source key [Silent Failure]", t_dispatch_labels_outputs),
    ("[integration] route-around 3 vendors, only OPENAI key", t_integration_route_around_three_vendors_one_key),
    ("[integration] delegate with dark pool raises (no hollow answer)", t_integration_delegate_all_dark_raises),
    ("[integration] unknown assigned_to via model_validate round-trip", t_integration_unknown_key_via_model_validate),
]


def main() -> int:
    """Run every test, print PASS/FAIL per case, and return a process exit code."""
    saved_env = dict(os.environ)
    passed = 0
    try:
        for name, fn in TESTS:
            try:
                fn()
                print(f"PASS  {name}")
                passed += 1
            except Exception:
                print(f"FAIL  {name}")
                traceback.print_exc()
    finally:
        os.environ.clear()
        os.environ.update(saved_env)
    total = len(TESTS)
    print(f"\n{passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
