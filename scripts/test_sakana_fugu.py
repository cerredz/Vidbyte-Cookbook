"""Deterministic, offline verification of the Sakana Fugu orchestration core.

Loads sdk/sakana-fugu/sakana_fugu.ipynb, execs ONLY the cells marked
`# [fugu-core]` (which import just the stdlib, no vidbyte), and drives
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
    ns: dict = {"__name__": "fugu_core"}  # not "__main__": skip the cell's live wiring block.
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
PoolModel = CORE["PoolModel"]
PROVIDER_ENV = CORE["PROVIDER_ENV"]


# --------------------------------------------------------------------------- #
# Fakes — duck-typed agents (anything with .run(str) -> reply.content)
# --------------------------------------------------------------------------- #
class Reply:
    def __init__(self, content=""):
        self.content = content


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


def pm(key, provider, agent):
    return PoolModel(key=key, provider=provider, agent=agent)


def set_providers(*providers):
    """Make exactly these providers 'available' by setting their key env vars; clear the rest."""
    for env_var in PROVIDER_ENV.values():
        os.environ.pop(env_var, None)
    for p in providers:
        os.environ[PROVIDER_ENV[p]] = "test-key"


# --------------------------------------------------------------------------- #
# Tests  (name, fn)  — fn raises AssertionError on failure
# --------------------------------------------------------------------------- #
def t_orchestrate_calls_every_available_expert_and_synthesizes():
    set_providers("openai", "anthropic")
    a, c, synth = FakeAgent("A"), FakeAgent("C"), FakeAgent("FINAL")
    f = Fugu([pm("reasoning", "anthropic", a), pm("coding", "openai", c)], synth)
    out = f.run("hard")
    assert out == "FINAL", out
    assert a.calls == 1 and c.calls == 1, "every available expert must be called once"
    assert synth.calls == 1, "synthesizer must run once"
    assert "[reasoning] A" in synth.prompts[0] and "[coding] C" in synth.prompts[0], "synth must receive labeled expert outputs"


def t_skips_experts_whose_provider_key_absent():
    set_providers("openai")  # anthropic absent
    r, c, synth = FakeAgent("R"), FakeAgent("C"), FakeAgent("FINAL")
    f = Fugu([pm("reasoning", "anthropic", r), pm("coding", "openai", c)], synth)
    out = f.run("x")
    assert r.calls == 0, "expert whose provider key is absent must not be called"
    assert c.calls == 1, "expert whose provider key is present must be called"
    assert synth.calls == 1 and out == "FINAL"


def t_ultra_runs_verifier_else_not():
    set_providers("openai")
    base = Fugu([pm("coding", "openai", FakeAgent("E"))], FakeAgent("DRAFT"))
    assert base.run("x") == "DRAFT", "base tier must not verify"
    ver = FakeAgent("VERIFIED")
    ultra = Fugu([pm("coding", "openai", FakeAgent("E"))], FakeAgent("DRAFT"), verifier=ver, ultra=True)
    assert ultra.run("x") == "VERIFIED"
    assert ver.calls == 1


def t_no_available_expert_raises():
    set_providers()  # clear all
    f = Fugu([pm("coding", "openai", FakeAgent("X"))], FakeAgent("S"))
    try:
        f.run("x")
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError when no expert is available")


def t_excluded_expert_not_called():
    set_providers("openai", "anthropic")
    a, c, synth = FakeAgent("A"), FakeAgent("C"), FakeAgent("FINAL")
    f = Fugu([pm("reasoning", "anthropic", a), pm("coding", "openai", c)], synth, exclude={"reasoning"})
    out = f.run("x")
    assert a.calls == 0, "opted-out expert must not be called even with its key present"
    assert c.calls == 1, "non-excluded available expert must be called"
    assert synth.calls == 1 and out == "FINAL"


# ---- integration ---------------------------------------------------------- #
def t_integration_one_key_only_openai_expert_called():
    set_providers("openai")  # the headline scenario: only OpenAI present
    r, c, l, synth = FakeAgent("R"), FakeAgent("C"), FakeAgent("L"), FakeAgent("FINAL")
    pool = [pm("reasoning", "anthropic", r), pm("coding", "openai", c), pm("long_context", "gemini", l)]
    f = Fugu(pool, synth)
    out = f.run("x")
    assert c.calls == 1, "only the available (OpenAI) expert must be called"
    assert r.calls == 0 and l.calls == 0, "experts without their provider key must not be called"
    assert synth.calls == 1 and out == "FINAL"


def t_integration_dark_pool_raises():
    set_providers()  # every provider unavailable
    synth = FakeAgent("FINAL")
    f = Fugu([pm("reasoning", "anthropic", FakeAgent("R"))], synth)
    try:
        f.run("x")
    except RuntimeError:
        assert synth.calls == 0, "must not synthesize a hollow answer when the pool is dark"
        return
    raise AssertionError("expected RuntimeError when no expert is available")


TESTS = [
    ("orchestrate calls every available expert and synthesizes [happy]", t_orchestrate_calls_every_available_expert_and_synthesizes),
    ("skips experts whose provider key is absent [Hidden Assumption]", t_skips_experts_whose_provider_key_absent),
    ("ultra runs verifier; base tier does not [Edge Case]", t_ultra_runs_verifier_else_not),
    ("run raises when no expert available [Silent Failure]", t_no_available_expert_raises),
    ("excluded (opted-out) expert is not called [Hidden Assumption]", t_excluded_expert_not_called),
    ("[integration] only OPENAI key -> only openai expert called", t_integration_one_key_only_openai_expert_called),
    ("[integration] dark pool raises (no hollow answer)", t_integration_dark_pool_raises),
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
