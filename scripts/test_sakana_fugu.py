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
PoolModel = CORE["PoolModel"]
PROVIDER_ENV = CORE["PROVIDER_ENV"]


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


def plan_delegate():
    return OrchestrationPlan(mode="delegate", reasoning="hard")


# --------------------------------------------------------------------------- #
# Tests  (name, fn)  — fn raises AssertionError on failure
# --------------------------------------------------------------------------- #
def t_direct_returns_one_string_no_synthesis():
    set_providers("openai")
    synth, member = FakeAgent("SYNTH"), FakeAgent("DIRECT-ANSWER")
    f = Fugu(OrchestratorFake(plan_direct()), [pm("coding", "openai", member)], synth)
    out = f.run("hi")
    assert out == "DIRECT-ANSWER", out
    assert synth.calls == 0, "synthesizer must not run in direct mode"
    assert member.calls == 1


def t_delegate_calls_all_available_and_synthesizes():
    set_providers("openai", "anthropic")
    a, c, synth = FakeAgent("A"), FakeAgent("C"), FakeAgent("FINAL")
    f = Fugu(OrchestratorFake(plan_delegate()), [pm("reasoning", "anthropic", a), pm("coding", "openai", c)], synth)
    out = f.run("hard")
    assert out == "FINAL", out
    assert a.calls == 1 and c.calls == 1, "every available expert must be called once"
    assert synth.calls == 1, "synthesizer must run once in delegate mode"
    assert "[reasoning] A" in synth.prompts[0] and "[coding] C" in synth.prompts[0], "synth must receive labeled expert outputs"


def t_delegate_skips_unavailable_providers():
    set_providers("openai")  # anthropic absent
    r, c, synth = FakeAgent("R"), FakeAgent("C"), FakeAgent("FINAL")
    f = Fugu(OrchestratorFake(plan_delegate()), [pm("reasoning", "anthropic", r), pm("coding", "openai", c)], synth)
    out = f.run("x")
    assert r.calls == 0, "unavailable provider must not be called"
    assert c.calls == 1, "available provider must be called"
    assert synth.calls == 1 and out == "FINAL"


def t_ultra_runs_verifier_else_not():
    set_providers("openai")
    base = Fugu(OrchestratorFake(plan_delegate()), [pm("coding", "openai", FakeAgent("E"))], FakeAgent("DRAFT"))
    assert base.run("x") == "DRAFT", "base tier must not verify"
    ver = FakeAgent("VERIFIED")
    ultra = Fugu(OrchestratorFake(plan_delegate()), [pm("coding", "openai", FakeAgent("E"))],
                 FakeAgent("DRAFT"), verifier=ver, ultra=True)
    assert ultra.run("x") == "VERIFIED"
    assert ver.calls == 1


def t_orchestrate_fallback_on_missing_structured():
    set_providers("openai")
    member, synth = FakeAgent("DIRECT"), FakeAgent("SYNTH")
    out = Fugu(NoStructuredOrchestrator(), [pm("coding", "openai", member)], synth).run("x")
    assert out == "DIRECT", "missing structured output must fall back to direct"
    assert synth.calls == 0


def t_no_available_model_raises():
    set_providers()  # clear all
    f = Fugu(OrchestratorFake(plan_direct()), [pm("coding", "openai", FakeAgent("X"))], FakeAgent("S"))
    try:
        f.run("x")
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError when no model is available")


def t_excluded_member_not_called():
    set_providers("openai", "anthropic")
    a, c, synth = FakeAgent("A"), FakeAgent("C"), FakeAgent("FINAL")
    f = Fugu(OrchestratorFake(plan_delegate()),
             [pm("reasoning", "anthropic", a), pm("coding", "openai", c)], synth, exclude={"reasoning"})
    out = f.run("x")
    assert a.calls == 0, "opted-out member must not be called even with its key present"
    assert c.calls == 1, "non-excluded available member must be called"
    assert synth.calls == 1 and out == "FINAL"


# ---- integration ---------------------------------------------------------- #
def t_integration_one_key_only_openai_expert_called():
    set_providers("openai")  # the headline scenario: only OpenAI present
    r, c, l, synth = FakeAgent("R"), FakeAgent("C"), FakeAgent("L"), FakeAgent("FINAL")
    pool = [pm("reasoning", "anthropic", r), pm("coding", "openai", c), pm("long_context", "gemini", l)]
    f = Fugu(OrchestratorFake(plan_delegate()), pool, synth)
    out = f.run("x")
    assert c.calls == 1, "only the available (OpenAI) expert must be called"
    assert r.calls == 0 and l.calls == 0, "unavailable vendors must not be called"
    assert synth.calls == 1 and out == "FINAL"


def t_integration_delegate_dark_pool_raises():
    set_providers()  # every provider unavailable
    synth = FakeAgent("FINAL")
    f = Fugu(OrchestratorFake(plan_delegate()), [pm("reasoning", "anthropic", FakeAgent("R"))], synth)
    try:
        f.run("x")
    except RuntimeError:
        assert synth.calls == 0, "must not synthesize a hollow answer when the pool is dark"
        return
    raise AssertionError("expected RuntimeError when delegating with no available model")


def t_integration_plan_via_model_validate():
    set_providers("openai")
    c, synth = FakeAgent("C"), FakeAgent("FINAL")
    raw = {"mode": "delegate", "reasoning": "r"}
    plan = OrchestrationPlan.model_validate(raw)  # real round-trip, as the SDK would produce
    f = Fugu(OrchestratorFake(plan), [pm("coding", "openai", c)], synth)
    out = f.run("x")
    assert c.calls == 1
    assert out == "FINAL"


TESTS = [
    ("direct mode returns one string, no synthesis [Edge Case]", t_direct_returns_one_string_no_synthesis),
    ("delegate calls every available expert and synthesizes [happy]", t_delegate_calls_all_available_and_synthesizes),
    ("delegate skips experts whose provider key is absent [Hidden Assumption]", t_delegate_skips_unavailable_providers),
    ("ultra runs verifier; base tier does not [Edge Case]", t_ultra_runs_verifier_else_not),
    ("orchestrate falls back to direct on missing structured [Silent Failure]", t_orchestrate_fallback_on_missing_structured),
    ("run raises when no model available [Silent Failure]", t_no_available_model_raises),
    ("excluded (opted-out) member is not called [Hidden Assumption]", t_excluded_member_not_called),
    ("[integration] only OPENAI key -> only openai expert called", t_integration_one_key_only_openai_expert_called),
    ("[integration] delegate with dark pool raises (no hollow answer)", t_integration_delegate_dark_pool_raises),
    ("[integration] delegate plan via model_validate round-trip", t_integration_plan_via_model_validate),
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
