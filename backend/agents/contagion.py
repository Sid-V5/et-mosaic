# pyre-ignore-all-errors
"""
Contagion Agent — sector ripple analysis.
Classifies whether a signal is isolated, spreading, or systemic.
"""

import asyncio
import json
import os
import random
import logging
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Known company-name → NSE ticker mapping for reliable peer checks
_COMPANY_TICKER_MAP = {
    "tata consultancy services": "TCS", "tcs": "TCS",
    "infosys": "INFY", "wipro": "WIPRO", "hcl technologies": "HCLTECH",
    "reliance industries": "RELIANCE", "reliance": "RELIANCE",
    "hdfc bank": "HDFCBANK", "icici bank": "ICICIBANK", "sbi": "SBIN",
    "state bank of india": "SBIN", "kotak mahindra bank": "KOTAKBANK",
    "axis bank": "AXISBANK", "tata steel": "TATASTEEL",
    "hindalco": "HINDALCO", "vedanta": "VEDL", "jsw steel": "JSWSTEEL",
    "sun pharma": "SUNPHARMA", "cipla": "CIPLA", "dr reddy": "DRREDDY",
    "maruti suzuki": "MARUTI", "tata motors": "TATAMOTORS",
    "mahindra": "M&M", "bajaj auto": "BAJAJ-AUTO",
    "hindustan unilever": "HINDUNILVR", "itc": "ITC",
    "larsen & toubro": "LT", "adani enterprises": "ADANIENT",
    "bharti airtel": "BHARTIARTL", "ntpc": "NTPC", "ongc": "ONGC",
    "bpcl": "BPCL", "hpcl": "HPCL", "gail": "GAIL",
    "power grid": "POWERGRID", "coal india": "COALINDIA",
    "bajaj finance": "BAJFINANCE", "sbi life": "SBILIFE",
    "tech mahindra": "TECHM", "ultratech cement": "ULTRACEMCO",
    "apollo hospitals": "APOLLOHOSP", "titan": "TITAN",
}

class ContagionAgent:

    def __init__(self, chroma_store=None):
        from utils.groq_pool import get_groq_client
        self.client = get_groq_client()
        self.chroma_store = chroma_store

    def _get_dynamic_peers(self, company: str, sector: str, cached_articles: dict = None) -> list[str]:
        """Dynamically find related companies in the same sector from recent news.
        Uses cached_articles to avoid repeated DB calls."""
        peers = set()
        stored = cached_articles
        if stored is None and self.chroma_store:
            stored = self.chroma_store.get_recent_articles(days=7)
        if stored and stored.get("metadatas"):
            for m in stored["metadatas"]:
                if m.get("sector") == sector:
                    try:
                        comps = json.loads(m.get("company_names", "[]"))
                        if isinstance(comps, list):
                            for c in comps:
                                if c.lower() != company.lower():
                                    peers.add(c)
                    except Exception:
                        pass
        return list(peers)[:10]

    async def _check_peer(self, peer: str, peer_ticker: str, cached_articles: dict = None) -> dict:
        """Check a single peer for negative signals.
        Uses cached_articles to avoid repeated DB calls (fixes O(n²) issue)."""
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

            # Check cached articles for peer mentions
            stored = cached_articles
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

        # Cache stored articles once, pass to all sub-methods
        cached_articles = None
        if self.chroma_store:
            cached_articles = self.chroma_store.get_recent_articles(days=7)

        # Get sector peers (these ARE tickers from SECTOR_PEERS dict) 
        sector_peers = get_sector_peers(company, sector)
        # Dynamic peers may be company names, not tickers — keep them separate
        dynamic_peers = self._get_dynamic_peers(company, sector, cached_articles)
        
        # sector_peers are already tickers — check them with proper ticker format
        peer_tasks = []
        for peer_ticker in sector_peers[:6]:
            peer_tasks.append(self._check_peer(peer_ticker, peer_ticker, cached_articles))
        
        # For dynamic peers (company names), resolve to known tickers
        for peer_name in dynamic_peers[:4]:
            # Look up known ticker first, then fall back to guessing
            resolved_ticker = _COMPANY_TICKER_MAP.get(peer_name.lower(), "")
            if not resolved_ticker:
                # Skip peers without known tickers — prevents wasted yfinance calls
                continue
            peer_tasks.append(self._check_peer(peer_name, resolved_ticker, cached_articles))

        if not peer_tasks:
            return {
                "contagion_type": "isolated",
                "affected_peers": [],
                "contagion_note": f"Signal isolated to {company}.",
                "ripple_companies": [],
            }

        # Check all peers in parallel (tasks already built above)
        peer_results = await asyncio.gather(*peer_tasks, return_exceptions=True)

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
                        attempt = contagion_models.index(model_name)
                        delay = (2 ** attempt) + random.uniform(0, 1)
                        logger.warning(f"Contagion: rate limited on {model_name}, retrying in {delay:.1f}s...")
                        await asyncio.sleep(delay)
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
            "ripple_companies": sector_peers + dynamic_peers,
        }
