# Paper → Quiz — a typed two-stage pipeline with context primitives

Turn a research paper into a validated, concept-tagged multiple-choice quiz.
Two agents run in sequence, and every model output is **schema-validated**
before the next stage consumes it — no JSON-parsing string surgery anywhere.

```
paper.md ──▶ Stage 1: digest agent ──▶ PaperDigest ──▶ Stage 2: quiz agent ──▶ Quiz ──▶ quiz.json
             ContextManager(            (claims,         output_schema=Quiz     (validated
             FileContextItem +           terms,                                   items)
             TaskContextItem)            findings)
```

## What it demonstrates

- **`ContextManager` + context primitives** — the paper enters the agent's
  context as a structured `FileContextItem`, and the job description as a
  `TaskContextItem`, instead of being pasted into a prompt string.
- **`output_schema` structured output** — both stages pass a Pydantic model;
  the validated result arrives on `reply.metadata["structured"]`. Stage 2
  consumes Stage 1's typed digest, so the pipeline is composable.
- **Extract-then-generate** — digesting first yields better quizzes than
  one-shot generation: questions target the paper's actual claims and
  caveats rather than surface phrasing, and the intermediate digest is a
  reusable artifact in its own right.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY (or switch provider in .env)
jupyter lab paper_to_quiz.ipynb
```

The notebook uses the bundled sample paper by default; point `PAPER_PATH` at
your own markdown / plain-text paper to quiz something else.

Output lands in `quiz.json`. If `VIDBYTE_API_URL` / `VIDBYTE_API_KEY` are
set, the quiz is also POSTed to the Vidbyte platform so it gets a hosted,
shareable page and feeds the learner-state scheduler.

## Why this shape matters

A quiz generated from a digest inherits the digest's honesty: each question
carries the concept it tests and the claim it's grounded in, which is
exactly what a spaced-repetition system (see
[`../study-agent`](../study-agent/)) needs to schedule it against a
learner's gap map.

## Adapt it

- Swap the Pydantic schemas — cloze deletions, free-recall prompts, or exam
  blueprints are one schema change away.
- Run Stage 1 over a whole folder of PDFs (parse with `docling` or
  `markitdown` first) to build a course-sized question bank.
- Feed `PaperDigest.key_terms` into a glossary pipeline.
