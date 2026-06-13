# Vidbyte API Examples

Examples for the **Vidbyte API** — the REST and MCP surface of the Vidbyte
learning platform.

## What the API gives you

- **Content generation**: quizzes, exams, roadmaps, and quick-hits generated
  from a topic, document, or video transcript, grounded in learning-science
  defaults (retrieval practice, desirable difficulties, interleaving).
- **Learner state**: persistent, per-user knowledge state — mastery per
  concept, spaced-repetition schedule, calibration, and a gap map — readable
  and writable by your application or agent.
- **MCP server**: the same capabilities exposed as MCP tools, so any
  MCP-capable agent (Claude, ChatGPT, your own) can generate study material
  and query learner context directly.

## Planned examples

| Example | What it shows |
|---|---|
| `quickstart-quiz/` | Authenticate and generate your first quiz from a topic string via REST. |
| `transcript-to-exam/` | Turn a lecture transcript into a full exam with per-question concept tags. |
| `learner-state/` | Read a user's gap map and review queue; record review outcomes. |
| `mcp-connect/` | Connect the Vidbyte MCP server to an MCP-capable client and drive it from a conversation. |
| `webhooks/` | React to completed study sessions in your own backend. |

## Status

This folder is being populated. The SDK examples in
[`../sdk/`](../sdk/) already demonstrate the tools-over-real-systems pattern
these examples will use, and are the best starting point today.
