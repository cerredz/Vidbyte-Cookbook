# Socratic Tutor Swarm — multi-agent tutoring on the Actor runtime

A tutor that never just tells you the answer. Built on `vidbyte-sdk`'s
**`ActorRuntime`**: a coordinator agent delegates each turn to specialized
sub-actors running as asynchronous message-passing actors, then synthesizes
their work into one Socratic response.

```
                       ┌────────────────────────┐
        you ─────────▶ │  tutor-coordinator     │ ◀─ synthesizes the turn
                       │  (ActorRuntime, P2P)   │
                       └───┬────────┬───────┬───┘
              async msgs   │        │       │
                           ▼        ▼       ▼
                     explainer  question  misconception
                                 -writer   -checker
```

- **explainer** — builds the cleanest correct explanation of the concept,
  held in reserve so the coordinator can calibrate its hints.
- **question-writer** — drafts the next probing question, pitched just
  beyond what the learner has already demonstrated.
- **misconception-checker** — examines the learner's last answer for
  specific, named misconceptions rather than generic wrongness.

## What it demonstrates

- **`ActorRuntime`** — swapping the execution loop is one constructor
  argument. The same `BaseAgent` class runs linear by default; here it runs
  an asynchronous actor-model swarm with dynamically spawned workers.
- **`dynamic_actors=True`** — the coordinator spins up the sub-actors it
  needs for the turn rather than using a fixed pipeline.
- **`termination_mode="quiescence"`** — the turn ends when the actor system
  goes quiet (no in-flight messages), not when a fixed step count runs out.
- **Cheap workers, smart coordinator** — `worker_model` lets sub-actors run
  on a faster, cheaper model than the coordinator that synthesizes them.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY (or switch provider in .env)
jupyter lab socratic_tutor_swarm.ipynb
```

Each notebook cell is one conversational turn — edit `my_reply` and re-run
to keep the dialogue going.

## Sample session

```
you> can you explain why spaced repetition works?

tutor> Before I explain anything — you've clearly heard the term. What's
       your current guess: why would reviewing something *after* you've
       started to forget it beat reviewing it while it's still fresh?

you> maybe because it's harder so your brain works more?

tutor> That's genuinely close — effort is the right scent. Now sharpen it:
       harder *at what*, exactly? What is your brain doing during recall
       that it isn't doing during re-reading?
```

## Adapt it

- Add a `learner-state` actor that queries the Vidbyte API (see
  [`../study-agent`](../study-agent/)) so probing questions target the
  learner's actual gap map.
- Switch `topology` to broadcast for a panel-discussion dynamic.
- Raise `max_loop` and lower `worker_model` cost for deeper deliberation
  per turn.
