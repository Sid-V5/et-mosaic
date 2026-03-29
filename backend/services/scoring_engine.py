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

_CONTAGION_SCORE = {
    "isolated":  0.0,
    "spreading": 40.0,  # Meaningful contribution to ranking
    "systemic":  80.0,  # Systemic events dominate ranking
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

                # ── Contagion impact score ─────────────────────
                contagion_type = signal.get("contagion_type", "isolated")
                contagion_score = _CONTAGION_SCORE.get(contagion_type, 0.0)

                # ── Historical accuracy weight ───────────────────
                signal_type = signal.get("signal_type", "")
                accuracy = float(
                    self.accuracy_data.get(signal_type, {}).get("accuracy", 50)
                )

                # ── Portfolio relevance ──────────────────────────
                tickers = signal.get("nse_tickers", [])
                if not isinstance(tickers, (list, tuple)):
                    tickers = []
                portfolio_score = 0.0
                
                portfolio_match_type = "none"
                matched_holdings = []

                if portfolio_upper:
                    # Direct ticker match
                    direct_matches = [
                        str(t).upper() for t in tickers
                        if t is not None and str(t).upper() in portfolio_upper
                    ]
                    if direct_matches:
                        portfolio_score = 100.0
                        portfolio_match_type = "direct"
                        matched_holdings = direct_matches
                    else:
                        # Sector-level match: signal affects same sector as a portfolio holding
                        signal_sector = signal.get("sector", "Other")
                        if signal_sector != "Other":
                            from tools.nse_tools import SECTOR_PEERS
                            sector_tickers = set()
                            for s, peers in SECTOR_PEERS.items():
                                if s == signal_sector:
                                    sector_tickers.update(p.upper() for p in peers)
                            sector_matches = portfolio_upper & sector_tickers
                            if sector_matches:
                                portfolio_score = 50.0  # Half weight for sector-level
                                portfolio_match_type = "sector"
                                matched_holdings = list(sector_matches)

                signal["portfolio_relevance"] = portfolio_match_type
                signal["matched_holdings"] = matched_holdings

                # ── Composite score ──────────────────────────────
                composite = (
                    freshness_score * _WEIGHTS["freshness"]
                    + confidence * _WEIGHTS["confidence"]
                    + accuracy * _WEIGHTS["accuracy"]
                    + portfolio_score * _WEIGHTS["portfolio"]
                    + contagion_score * _WEIGHTS["contagion"]
                )

                # ── Freshness label ──────────────────────────────
                signal["freshness"] = self._freshness_label(hours_old)

                # BREAKING bonus: signals < 1 hour old get a +15 composite boost
                if signal["freshness"] == "BREAKING":
                    composite += 15.0

                signal["composite_score"] = round(float(composite), 2)

                scored.append(signal)

            except Exception as e:
                logger.error(f"Scoring error: {e}")
                signal["composite_score"] = 0
                scored.append(signal)

        # Sort: portfolio direct first, then sector, then by composite score descending
        scored.sort(key=lambda s: (
            {"direct": 0, "sector": 1, "none": 2}.get(s.get("portfolio_relevance", "none"), 2),
            -s.get("composite_score", 0),
        ))

        return scored

    def estimate_portfolio_impact(
        self,
        signal: dict,
        portfolio: list[str],
        portfolio_values: Optional[dict] = None,
    ) -> dict:
        """
        Scenario 3: Estimate quantified P&L impact of a signal on a user's portfolio.
        Uses sector beta for sensitivity estimation.
        
        Args:
            signal: The signal card dict
            portfolio: List of ticker symbols the user holds
            portfolio_values: Optional {ticker: invested_value_in_INR} map
                             Defaults to equal-weight ₹1,00,000 per stock if not provided
        Returns:
            dict with estimated_impact_pct, estimated_impact_inr, materiality_rank
        """
        from tools.nse_tools import get_sector_beta, SECTOR_PEERS

        if not portfolio:
            return {"estimated_impact_pct": 0, "estimated_impact_inr": 0, "materiality": "NONE"}

        # Default: equal-weight ₹1L per stock
        if not portfolio_values:
            portfolio_values = {t.upper(): 100000 for t in portfolio}
        total_portfolio = sum(portfolio_values.values())

        signal_sector = signal.get("sector", "Other")
        severity = signal.get("severity", "medium")
        confidence = float(signal.get("confidence", 50)) / 100

        # Severity → expected price move (conservative estimates)
        severity_impact = {"high": -0.05, "medium": -0.02, "low": -0.01}
        base_impact = severity_impact.get(severity, -0.02)

        # Adjust for signal type sentiment
        signal_type = signal.get("signal_type", "")
        if signal_type in ["SILENT_ACCUMULATION"]:
            base_impact = abs(base_impact)  # Accumulation is bullish

        sector_beta = get_sector_beta(signal_sector)

        # Calculate per-holding impact
        impacts = []
        for ticker in portfolio:
            ticker_up = ticker.upper()
            position_value = portfolio_values.get(ticker_up, 100000)
            weight = position_value / total_portfolio if total_portfolio > 0 else 0

            # Check direct vs sector exposure
            tickers_in_signal = [str(t).upper() for t in signal.get("nse_tickers", []) if t]
            if ticker_up in tickers_in_signal:
                # Direct impact: full severity * beta * confidence
                stock_impact_pct = base_impact * sector_beta * confidence
            else:
                # Sector contagion: check if same sector
                is_same_sector = False
                for s, peers in SECTOR_PEERS.items():
                    if s == signal_sector and ticker_up in [p.upper() for p in peers]:
                        is_same_sector = True
                        break
                if is_same_sector:
                    stock_impact_pct = base_impact * sector_beta * confidence * 0.4  # 40% contagion
                else:
                    stock_impact_pct = 0  # No impact on unrelated sectors

            if stock_impact_pct != 0:
                impact_inr = round(position_value * stock_impact_pct)
                impacts.append({
                    "ticker": ticker_up,
                    "position_value": position_value,
                    "estimated_impact_pct": round(stock_impact_pct * 100, 2),
                    "estimated_impact_inr": impact_inr,
                })

        total_impact_inr = sum(i["estimated_impact_inr"] for i in impacts)
        total_impact_pct = round((total_impact_inr / total_portfolio * 100), 2) if total_portfolio > 0 else 0

        # Materiality classification
        if abs(total_impact_pct) >= 2:
            materiality = "HIGH"
        elif abs(total_impact_pct) >= 0.5:
            materiality = "MEDIUM"
        elif abs(total_impact_pct) > 0:
            materiality = "LOW"
        else:
            materiality = "NONE"

        return {
            "affected_holdings": impacts,
            "total_impact_inr": total_impact_inr,
            "total_impact_pct": total_impact_pct,
            "materiality": materiality,
            "total_portfolio_value": total_portfolio,
        }

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

