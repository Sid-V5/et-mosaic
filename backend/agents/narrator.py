# pyre-ignore-all-errors
"""
Narrator Agent — generates signal cards and Hindi TTS audio.
Uses Groq 70B for narrative generation and gTTS for Hindi audio.
Validates output with Pydantic SignalCard before returning.
"""

import asyncio
import json
import os
import logging
from groq import AsyncGroq
from dotenv import load_dotenv
from models.schemas import SignalCard, ActionRecommendation
from tools.nse_tools import get_sector_peers

load_dotenv()
logger = logging.getLogger(__name__)

NARRATOR_PROMPT = """You are ET Mosaic Narrator. Persona: honest CFA-holding friend. Rules: never say buy or sell; always cite sources; max 8-word headline in active voice; summary = exactly 2 sentences (S1: what data shows, S2: historical base rate with % accuracy); what_to_watch = 1 specific measurable thing; always end with: This is for research only. Not investment advice. Return ONLY JSON: {headline, summary, what_to_watch, action_recommendation: {type: ADD_WATCHLIST or REDUCE_EXPOSURE or INCREASE_MONITORING, reasoning}}."""


class NarratorAgent:

    def __init__(self):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

    async def _narrate_one(self, signal: dict, portfolio: list[str]) -> dict:
        """Generate a single signal card."""
        try:
            evidence = json.dumps({
                "companies": signal.get("company_names", []),
                "signal_type": signal.get("signal_type", ""),
                "confidence": signal.get("confidence", 0),
                "severity": signal.get("severity", "medium"),
                "explanation": signal.get("explanation", ""),
                "sources": signal.get("sources", []),
                "bulk_deals": signal.get("bulk_deals", []),
                "technical": signal.get("technical", {}),
                "contagion_note": signal.get("contagion_note", ""),
                "historical_accuracy": signal.get("historical_match", 0),
            }, default=str)

            # Model fallback chain — ordered by TPM limit
            narrator_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
            response = None
            for model_name in narrator_models:
                try:
                    response = await self.client.chat.completions.create(
                        model=model_name,
                        temperature=0.1,
                        max_tokens=1024, # Increased massively from 400 to prevent JSON cutoffs
                        messages=[
                            {"role": "system", "content": NARRATOR_PROMPT},
                            {"role": "user", "content": evidence},
                        ],
                    )
                    break
                except Exception as me:
                    logger.warning(f"Narrator failed on {model_name}: {me}, trying next...")
                    await asyncio.sleep(1)
                    continue
            if response is None:
                raise Exception("All models rate limited")

            text = response.choices[0].message.content.strip()
            # Robust JSON extraction — strip markdown fences, then brace-match
            import re
            text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.MULTILINE)
            text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
            text = text.strip()
            
            card_data = {}
            # Try direct parse first
            try:
                card_data = json.loads(text)
            except json.JSONDecodeError:
                # Find outermost JSON object via brace matching
                start = text.find('{')
                if start == -1:
                    logger.warning("No JSON object in narrator response")
                else:
                    depth = 0
                    for i in range(start, len(text)):
                        if text[i] == '{': depth += 1
                        elif text[i] == '}':
                            depth -= 1
                            if depth == 0:
                                try:
                                    card_data = json.loads(text[start:i + 1])
                                except Exception as json_err:
                                    logger.warning(f"Inner JSON decode failed: {json_err}")
                                break
                    else:
                        logger.warning("Incomplete JSON in narrator response")

            if not card_data:
                # Build fallback data without breaking entire signal card
                card_data = {
                    "headline": "Signal Detected: Unclear Context",
                    "summary": f"Signal extraction complete but logic engine failed to categorize. Type: {signal.get('signal_type', 'Unknown')}",
                    "what_to_watch": "Market volatility in connected vectors.",
                    "action_recommendation": {"type": "INCREASE_MONITORING", "reasoning": "Uncertain signal taxonomy."}
                }

            # Generate Hindi audio
            from tools.tts_tools import generate_hindi_audio
            import hashlib
            company = signal.get("company_names", [""])[0] if signal.get("company_names") else ""
            
            # Generate deterministic but unique ID based on ALL article IDs in the cluster
            article_ids_str = "".join(sorted([str(aid) for aid in signal.get("article_ids", [])]))
            signal_id = hashlib.md5(article_ids_str.encode()).hexdigest()[:8] if article_ids_str else "signal"

            summary_hindi = card_data.get("summary", "")
            headline_text = card_data.get("headline", "")
            what_to_watch_text = card_data.get("what_to_watch", "")
            audio_path = await generate_hindi_audio(
                signal_id, company, summary_hindi,
                signal.get("confidence", 0),
                headline=headline_text,
                what_to_watch=what_to_watch_text,
            )

            # Portfolio relevance: direct if company in portfolio, sector if peer of portfolio holding
            portfolio_upper = [p.upper() for p in portfolio] if portfolio else []
            tickers = [t.upper() for t in signal.get("nse_tickers", [])]
            if any(t in portfolio_upper for t in tickers):
                portfolio_relevance = "direct"
            elif portfolio_upper:
                # Check if signal company is a sector peer of any portfolio holding
                sector = signal.get("sector", "Other")
                try:
                    for pticker in portfolio_upper:
                        peers = get_sector_peers(pticker, sector)
                        peer_tickers = [p.upper() for p in peers]
                        if any(t in peer_tickers for t in tickers):
                            portfolio_relevance = "sector"
                            break
                    else:
                        portfolio_relevance = "none"
                except Exception:
                    portfolio_relevance = "none"
            else:
                portfolio_relevance = "none"

            # Build signal card
            action_rec = card_data.get("action_recommendation", {})
            if isinstance(action_rec, str):
                action_rec = {"type": "INCREASE_MONITORING", "reasoning": action_rec}

            card_dict = {
                "id": signal_id,
                "headline": card_data.get("headline", "Signal Detected"),
                "summary": card_data.get("summary", ""),
                "what_to_watch": card_data.get("what_to_watch", ""),
                "signal_type": signal.get("signal_type", "TRIPLE_THREAT"),
                "severity": signal.get("severity", "medium"),
                "freshness": "BREAKING" if signal.get("confidence", 0) > 75 else "RECENT",
                "confidence": signal.get("confidence", 0),
                "sources": signal.get("sources", []),
                "contagion_note": signal.get("contagion_note", ""),
                "historical_match": signal.get("historical_match", 0),
                "portfolio_relevance": portfolio_relevance,
                "action_recommendation": {
                    "type": action_rec.get("type", "INCREASE_MONITORING"),
                    "reasoning": action_rec.get("reasoning", ""),
                    "confidence": signal.get("confidence", 0),
                },
                "audio_path": audio_path,
                "disclaimer": "This is for research only. Not investment advice.",
                "company_names": signal.get("company_names", []),
                "nse_tickers": signal.get("nse_tickers", []),
                "bulk_deals": signal.get("bulk_deals", []),
                "price_data": signal.get("price_data", {}),
                "technical": signal.get("technical", {}),
                "contagion_type": signal.get("contagion_type", "isolated"),
                "affected_peers": signal.get("affected_peers", []),
                "created_at": signal.get("created_at", ""),
                # ── fields that were previously stripped ──
                "sector": signal.get("sector", "Other"),
                "event_types": signal.get("event_types", []),
                "market_data_confirmation": signal.get("market_data_confirmation", 0),
                "sentiment_velocity": signal.get("sentiment_velocity", 0),
                "similarity": signal.get("similarity", 0),
            }

            # Validate with Pydantic SignalCard before returning
            try:
                validated = SignalCard(**card_dict)
                return validated.model_dump()
            except Exception as val_err:
                logger.warning(f"Pydantic validation warning: {val_err}, returning unvalidated card")
                return card_dict

        except Exception as e:
            logger.error(f"Narration error: {e}")
            return {
                "id": signal.get("article_ids", ["err"])[0][:8] if signal.get("article_ids") else "error",
                "headline": "Signal requires manual review",
                "summary": signal.get("explanation", "Error generating narrative."),
                "what_to_watch": "Check source articles directly.",
                "signal_type": signal.get("signal_type", "TRIPLE_THREAT"),
                "severity": signal.get("severity", "medium"),
                "freshness": "RECENT",
                "confidence": signal.get("confidence", 0),
                "sources": signal.get("sources", []),
                "contagion_note": signal.get("contagion_note", ""),
                "historical_match": 0,
                "portfolio_relevance": "none",
                "action_recommendation": {"type": "INCREASE_MONITORING", "reasoning": "Auto-generated fallback.", "confidence": 0},
                "audio_path": "",
                "disclaimer": "This is for research only. Not investment advice.",
            }

    async def narrate_batch(self, signals: list, portfolio: list[str] = None) -> list[dict]:
        """Generate signal cards for top 5 signals in parallel."""
        if not signals:
            return []

        portfolio = portfolio or []
        top_signals = signals[:5]

        tasks = [self._narrate_one(s, portfolio) for s in top_signals]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        cards = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Narration exception: {r}")
                continue
            cards.append(r)

        # Sort: direct portfolio first, then sector, then none
        relevance_order = {"direct": 0, "sector": 1, "none": 2}
        cards.sort(key=lambda c: relevance_order.get(c.get("portfolio_relevance", "none"), 2))

        # Save to signals.json
        self._save_signals(cards)

        logger.info(f"Generated {len(cards)} signal cards")
        return cards

    def _save_signals(self, cards: list):
        """Save signal cards to signals.json."""
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        try:
            with open(os.path.join(data_dir, "signals.json"), "w") as f:
                json.dump(cards, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving signals.json: {e}")
