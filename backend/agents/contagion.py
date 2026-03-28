# pyre-ignore-all-errors
"""
Contagion Agent — sector ripple analysis.
Classifies whether a signal is isolated, spreading, or systemic.
"""

import asyncio
import json
import os
import logging
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Hardcoded supply chain relationships
SUPPLY_CHAIN = {
    "Vedanta": ["Hindustan Zinc"],
    "Hindalco": ["Novelis"],
    "Tata Sons": ["TCS", "Jaguar"],
    "Reliance": ["HPCL", "BPCL"],
    "SBI": ["SBI Life", "SBI Cards"],
    "Adani Enterprises": ["Adani Ports", "Adani Green", "Adani Power", "Adani Total Gas"],
    "HDFC Bank": ["HDFC Life", "HDFC AMC"],
    "ICICI Bank": ["ICICI Prudential", "ICICI Lombard"],
    "Bajaj Finance": ["Bajaj Finserv"],
    "Tata Motors": ["Tata Power", "Tata Steel"],
}


class ContagionAgent:

    def __init__(self, chroma_store=None):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.chroma_store = chroma_store

    def _get_supply_chain(self, company: str) -> list[str]:
        """Get supply chain related entities."""
        for key, values in SUPPLY_CHAIN.items():
            if company.lower() in key.lower() or key.lower() in company.lower():
                return values
        return []

    async def _check_peer(self, peer: str, peer_ticker: str) -> dict:
        """Check a single peer for negative signals."""
        from tools.nse_tools import fetch_price_volume
        result = {"peer": peer, "ticker": peer_ticker, "has_negative_signal": False, "details": ""}

        try:
            # Check price data
            price_data = await fetch_price_volume([peer_ticker])
            if peer_ticker in price_data:
                pd = price_data[peer_ticker]
                if pd.get("volume_spike"):
                    result["has_negative_signal"] = True
                    result["details"] += "Volume spike detected. "
                if pd.get("price_change_7d_pct", 0) < -5:
                    result["has_negative_signal"] = True
                    result["details"] += f"Price down {pd['price_change_7d_pct']}% in 7d. "

            # Check ChromaDB for recent articles mentioning peer
            if self.chroma_store:
                stored = self.chroma_store.get_recent_articles(days=7)
                if stored and stored.get("ids"):
                    for i, doc in enumerate(stored.get("documents", [])):
                        if doc and peer.lower() in doc.lower():
                            meta = stored["metadatas"][i] if stored.get("metadatas") else {}
                            if float(meta.get("sentiment", 0)) < -0.3:
                                result["has_negative_signal"] = True
                                result["details"] += f"Negative article found: {meta.get('title', '')[:50]}. "
                            break

        except Exception as e:
            logger.error(f"Peer check error for {peer}: {e}")

        return result

    async def propagate(self, signal: dict) -> dict:
        """Analyze contagion/ripple effects of a signal."""
        from tools.nse_tools import get_sector_peers

        company = signal.get("company_names", ["Unknown"])[0] if signal.get("company_names") else "Unknown"
        sector = signal.get("sector", "Other")
        ticker = signal.get("nse_tickers", [""])[0] if signal.get("nse_tickers") else ""

        # Get sector peers + supply chain entities
        sector_peers = get_sector_peers(company, sector)
        supply_chain = self._get_supply_chain(company)
        all_entities = list(set(sector_peers + supply_chain))

        if not all_entities:
            return {
                "contagion_type": "isolated",
                "affected_peers": [],
                "contagion_note": f"Signal isolated to {company}.",
                "ripple_companies": [],
            }

        # Check all peers in parallel
        tasks = [self._check_peer(p, p) for p in all_entities[:10]]
        peer_results = await asyncio.gather(*tasks, return_exceptions=True)

        negative_peers = []
        for r in peer_results:
            if isinstance(r, Exception):
                continue
            if r.get("has_negative_signal"):
                negative_peers.append(r["peer"])

        # Classify
        count = len(negative_peers)
        if count < 2:
            contagion_type = "isolated"
        elif count <= 4:
            contagion_type = "spreading"
        else:
            contagion_type = "systemic"

        # Generate contagion note via LLM (with model fallback)
        contagion_models = ["groq/compound-mini", "moonshotai/kimi-k2-instruct-0905", "llama-3.1-8b-instant"]
        try:
            prompt_text = f"Given signal about {company} and these peer findings: {json.dumps(negative_peers)}. Contagion type: {contagion_type}. Write a 1-sentence plain-English contagion note for a retail investor. Must be actionable. Max 20 words. If isolated: say isolated. If spreading/systemic: name the affected peers."

            response = None
            for model_name in contagion_models:
                try:
                    response = await self.client.chat.completions.create(
                        model=model_name,
                        temperature=0,
                        max_tokens=50,
                        messages=[
                            {"role": "system", "content": "You write concise financial alerts. Max 20 words. No markdown."},
                            {"role": "user", "content": prompt_text},
                        ],
                    )
                    break
                except Exception as me:
                    if "429" in str(me) or "rate_limit" in str(me).lower():
                        logger.warning(f"Contagion: rate limited on {model_name}, trying next...")
                        await asyncio.sleep(2)
                        continue
                    raise me
            if response is None:
                raise Exception("All models rate limited")
            contagion_note = response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Contagion LLM error: {e}")
            if contagion_type == "isolated":
                contagion_note = f"Signal isolated to {company}. No sector ripple detected."
            else:
                contagion_note = f"Signal spreading across {', '.join(negative_peers[:3])}. Monitor sector closely."

        return {
            "contagion_type": contagion_type,
            "affected_peers": negative_peers,
            "contagion_note": contagion_note,
            "ripple_companies": all_entities,
        }
