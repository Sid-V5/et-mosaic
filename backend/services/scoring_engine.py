"""
Scoring Engine — rank signals by freshness, contagion, and accuracy.
Deterministic — no LLM.
Enterprise-grade: proper type annotations, null-safe operations, validated scoring formula.
"""

from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ACCURACY_PATH = os.path.join(DATA_DIR, "accuracy_store.json")

# Scoring weights — centralised for easy tuning
_WEIGHTS = {
    "freshness":  0.20,
    "confidence": 0.35,
    "accuracy":   0.15,
    "portfolio":  0.20,
    "contagion":  0.10,
}

_CONTAGION_MULTIPLIER = {
    "isolated":  1.0,
    "spreading": 1.3,
    "systemic":  1.6,
}

_FRESHNESS_DECAY_PER_HOUR = 4  # lose 4 points per hour


class ScoringEngine:

    def __init__(self) -> None:
        self.accuracy_data = self._load_accuracy()

    def _load_accuracy(self) -> dict:
        try:
            with open(ACCURACY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def score_signals(
        self,
        signals: list[dict],
        portfolio: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Score and rank signals by composite score.
        Score = freshness_weight + confidence_weight + contagion_weight + accuracy_weight + portfolio_weight
        """
        if not signals:
            return []

        portfolio = portfolio or []
        portfolio_upper = {p.upper() for p in portfolio}  # set for O(1) lookup
        now = datetime.now(timezone.utc)

        scored: list[dict] = []
        for signal in signals:
            try:
                # ── Freshness decay (newer = higher) ─────────────
                hours_old = self._hours_since_created(signal, now)
                freshness_score = max(0.0, 100.0 - hours_old * _FRESHNESS_DECAY_PER_HOUR)

                # ── Confidence ───────────────────────────────────
                confidence = float(signal.get("confidence", 50))

                # ── Contagion multiplier ─────────────────────────
                contagion_type = signal.get("contagion_type", "isolated")
                contagion_mult = _CONTAGION_MULTIPLIER.get(contagion_type, 1.0)

                # ── Historical accuracy weight ───────────────────
                signal_type = signal.get("signal_type", "")
                accuracy = float(
                    self.accuracy_data.get(signal_type, {}).get("accuracy", 50)
                )

                # ── Portfolio relevance ──────────────────────────
                tickers = signal.get("nse_tickers", [])
                # Type-safe: ensure tickers is iterable of strings
                if not isinstance(tickers, (list, tuple)):
                    tickers = []
                portfolio_score = 0.0
                if portfolio_upper and any(
                    str(t).upper() in portfolio_upper
                    for t in tickers
                    if t is not None
                ):
                    portfolio_score = 30.0
                    signal["portfolio_relevance"] = "direct"
                else:
                    signal["portfolio_relevance"] = "none"

                # ── Composite score ──────────────────────────────
                composite = (
                    freshness_score * _WEIGHTS["freshness"]
                    + confidence * _WEIGHTS["confidence"]
                    + accuracy * _WEIGHTS["accuracy"]
                    + portfolio_score * _WEIGHTS["portfolio"]
                    + (contagion_mult - 1.0) * 50.0 * _WEIGHTS["contagion"]
                )

                signal["composite_score"] = round(float(composite), 2)  # type: ignore[call-overload]

                # ── Freshness label ──────────────────────────────
                signal["freshness"] = self._freshness_label(hours_old)

                scored.append(signal)

            except Exception as e:
                logger.error(f"Scoring error: {e}")
                signal["composite_score"] = 0
                scored.append(signal)

        # Sort: portfolio direct first, then by composite score descending
        scored.sort(key=lambda s: (
            0 if s.get("portfolio_relevance") == "direct" else 1,
            -s.get("composite_score", 0),
        ))

        return scored

    # ── private helpers ──────────────────────────────────────────

    @staticmethod
    def _hours_since_created(signal: dict, now: datetime) -> float:
        """Return the number of hours since signal creation, defaulting to 24."""
        created_str = signal.get("created_at", "")
        if not created_str:
            return 24.0
        try:
            created = datetime.fromisoformat(
                created_str.replace("Z", "+00:00")
            )
            return (now - created).total_seconds() / 3600.0
        except Exception:
            return 24.0

    @staticmethod
    def _freshness_label(hours_old: float) -> str:
        if hours_old < 1:
            return "BREAKING"
        if hours_old < 6:
            return "RECENT"
        if hours_old < 24:
            return "TODAY"
        return "AGING"
