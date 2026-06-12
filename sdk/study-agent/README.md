# Study Agent — a spaced-repetition coach with persistent learner state

An interactive study coach built with `vidbyte-sdk`. The agent's tools give
it access to a real spaced-repetition scheduler: it pulls the cards you're
due to review, quizzes you with retrieval practice (free recall before
recognition), grades your answers, and writes the outcome back so the
scheduler can pick the next due date.

This is the canonical "agent + learner state" pattern: the model provides
the conversation and judgment; the durable knowledge of *what you know and
when you'll forget it* lives behind the tools.

## Architecture

```
┌────────────┐   run()    ┌──────────────────────┐
│  You (CLI) │ ─────────▶ │  study-coach agent   │
└────────────┘            │  (BaseAgent, linear) │
                          └──────────┬───────────┘
                            tool calls │
            ┌──────────────────┬──────┴───────────┐
            ▼                  ▼                  ▼
   get_due_reviews()  get_learner_context()  record_review()
            └──────────────────┴──────────────────┘
                               │
                     VidbyteClient
            (live Vidbyte API when configured,
             local SM-2 deck in deck.json otherwise)
```

## What it demonstrates

- **`@tool` functions** — plain Python functions with type hints and
  docstrings become callable tools; the SDK handles schema description,
  formatting, and execution.
- **State behind tools** — the agent never "remembers" your mastery; it
  *reads* it. Swap the local stub for the live Vidbyte API and the agent
  code does not change.
- **A real session loop** — agent history persists across turns, so the
  coach can run a multi-card session conversationally.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY (or switch provider in .env)
jupyter lab study_agent.ipynb
```

Run the notebook cells top to bottom; the "Answer the card" cell is your
conversational turn — edit it and re-run for each card in the session.

Without Vidbyte API credentials the example seeds a small demo deck in
`deck.json` and schedules it with a compact SM-2 implementation, so the full
loop — due cards → quiz → grade → reschedule — works offline. Set
`VIDBYTE_API_URL` and `VIDBYTE_API_KEY` to run against the live platform
instead.

## Sample session

```
coach> You have 3 cards due. Let's start with the one you've struggled
       with: Without looking anything up — what does the "testing effect"
       say about retrieval vs. re-reading?

you> retrieving from memory strengthens it more than re-reading does

coach> Exactly right — recalled, not recognized, which is the strong form.
       Logged as "good"; you'll see it again in 6 days. Next card...
```

## Adapt it

- Point `VidbyteClient` at your own card store (Anki export, Notion DB).
- Add a `get_gap_map()` tool so the coach prioritizes weak concepts, not
  just due dates.
- Swap the CLI loop for a Slack bot or voice interface — the agent and
  tools are transport-agnostic.
