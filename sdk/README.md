# Vidbyte SDK Examples

Real-world agent setups built with **`vidbyte-sdk`**, the Python agent
framework. Install with `pip install vidbyte-sdk`; import as `vidbyte`:

```python
from vidbyte import BaseAgent, tool
```

Each example is a self-contained folder showcasing one distinctive SDK
capability while doing a job someone would actually want done:

| Example | SDK capability showcased | Real-world job |
|---|---|---|
| [`study-agent/`](study-agent/) | `@tool` functions + agent tool loop, persistent state behind tools | A spaced-repetition study coach that knows what you're due to review, quizzes you, and reschedules cards based on how you did. |
| [`paper-to-quiz/`](paper-to-quiz/) | `ContextManager` + `FileContextItem` / `TaskContextItem`, `output_schema` structured output | Turn a research paper into a validated, concept-tagged quiz — a two-stage extract-then-generate pipeline with typed outputs at every step. |
| [`socratic-tutor-swarm/`](socratic-tutor-swarm/) | `ActorRuntime` (async actor-model runtime, dynamic sub-actors) | A Socratic tutor where a coordinator delegates each turn to specialized sub-actors: explainer, question-writer, misconception-checker. |

## Common setup

Every example is a Jupyter notebook and follows the same contract:

```bash
cd <example>
pip install -r requirements.txt
cp .env.example .env     # add your provider key
jupyter lab <example>.ipynb   # then run the cells top to bottom
```

Provider and model are configured per-example via `.env`
(`VIDBYTE_COOKBOOK_PROVIDER`, `VIDBYTE_COOKBOOK_MODEL`); they default to
OpenAI. Examples that touch the Vidbyte platform use a small client that
calls the live API when `VIDBYTE_API_URL`/`VIDBYTE_API_KEY` are set and a
local stub otherwise — the agent code is identical in both modes.
