"""Learner-state client for the study agent.

Talks to the live Vidbyte API when VIDBYTE_API_URL / VIDBYTE_API_KEY are set.
Otherwise falls back to a local demo deck (deck.json) scheduled with a compact
SM-2 implementation, so the example runs end-to-end offline. The agent-facing
interface is identical in both modes.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DECK_PATH = Path(__file__).parent / "deck.json"

SEED_CARDS = [
    {
        "card_id": "testing-effect",
        "concept": "Testing effect",
        "prompt": "What does the testing effect say about retrieval practice vs. re-reading?",
        "answer": "Actively retrieving information from memory strengthens retention far more than passively re-reading it.",
    },
    {
        "card_id": "spacing-effect",
        "concept": "Spacing effect",
        "prompt": "Why does spacing study sessions out beat massing them together?",
        "answer": "Distributed practice forces effortful retrieval after partial forgetting, which produces more durable memory than cramming.",
    },
    {
        "card_id": "desirable-difficulties",
        "concept": "Desirable difficulties",
        "prompt": "What is a 'desirable difficulty' in learning?",
        "answer": "A condition that makes practice feel harder and slower (spacing, interleaving, testing) but improves long-term retention and transfer.",
    },
    {
        "card_id": "fluency-illusion",
        "concept": "Fluency illusion",
        "prompt": "What is the fluency illusion and why is it dangerous for learners?",
        "answer": "Mistaking ease of processing (smooth re-reading, highlighting) for actual learning; it leads learners to prefer strategies that feel good but don't work.",
    },
]

# SM-2-lite intervals: rating 0=forgot, 1=hard, 2=good, 3=easy
_EASE_DELTA = {0: -0.20, 1: -0.05, 2: 0.0, 3: 0.10}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class VidbyteClient:
    """Unified due-review / learner-context / record-review interface."""

    def __init__(self) -> None:
        self.api_url = os.getenv("VIDBYTE_API_URL", "").rstrip("/")
        self.api_key = os.getenv("VIDBYTE_API_KEY", "")
        self.live = bool(self.api_url and self.api_key)
        if not self.live:
            self._ensure_local_deck()

    # ── public interface (what the agent's tools call) ──────────────────

    def due_reviews(self, limit: int = 5) -> list[dict]:
        if self.live:
            return self._get("/v1/reviews/due", params={"limit": limit})
        deck = self._load_deck()
        now = _now().isoformat()
        due = [c for c in deck["cards"] if c["due"] <= now]
        due.sort(key=lambda c: c["ease"])  # hardest first
        return [
            {"card_id": c["card_id"], "concept": c["concept"], "prompt": c["prompt"], "answer": c["answer"]}
            for c in due[:limit]
        ]

    def learner_context(self, topic: str) -> dict:
        if self.live:
            return self._get("/v1/learner/context", params={"topic": topic})
        deck = self._load_deck()
        matching = [c for c in deck["cards"] if topic.lower() in c["concept"].lower()] or deck["cards"]
        return {
            "topic": topic,
            "concepts": [
                {"concept": c["concept"], "ease": c["ease"], "reviews": c["reviews"], "lapses": c["lapses"]}
                for c in matching
            ],
            "weakest": min(matching, key=lambda c: c["ease"])["concept"],
        }

    def record_review(self, card_id: str, rating: int) -> dict:
        rating = max(0, min(3, int(rating)))
        if self.live:
            return self._post("/v1/reviews", body={"card_id": card_id, "rating": rating})
        deck = self._load_deck()
        card = next((c for c in deck["cards"] if c["card_id"] == card_id), None)
        if card is None:
            return {"error": f"unknown card_id '{card_id}'"}

        card["ease"] = max(1.3, card["ease"] + _EASE_DELTA[rating])
        card["reviews"] += 1
        if rating == 0:
            card["lapses"] += 1
            card["interval_days"] = 1
        elif card["reviews"] == 1:
            card["interval_days"] = 1
        elif card["reviews"] == 2:
            card["interval_days"] = 3
        else:
            card["interval_days"] = round(card["interval_days"] * card["ease"], 1)
        card["due"] = (_now() + timedelta(days=card["interval_days"])).isoformat()
        self._save_deck(deck)
        return {"card_id": card_id, "rating": rating, "next_due_in_days": card["interval_days"]}

    # ── live API helpers ─────────────────────────────────────────────────

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        resp = requests.get(
            f"{self.api_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        resp = requests.post(
            f"{self.api_url}{path}",
            json=body,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ── local deck helpers ───────────────────────────────────────────────

    def _ensure_local_deck(self) -> None:
        if DECK_PATH.exists():
            return
        deck = {
            "cards": [
                {**card, "ease": 2.5, "interval_days": 0, "reviews": 0, "lapses": 0, "due": _now().isoformat()}
                for card in SEED_CARDS
            ]
        }
        self._save_deck(deck)

    def _load_deck(self) -> dict:
        return json.loads(DECK_PATH.read_text(encoding="utf-8"))

    def _save_deck(self, deck: dict) -> None:
        DECK_PATH.write_text(json.dumps(deck, indent=2), encoding="utf-8")
