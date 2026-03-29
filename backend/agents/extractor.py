# pyre-ignore-all-errors
"""
Extractor Agent — LLM-powered entity/event extraction from articles.
Uses Groq with smart model fallback chain to avoid rate limits.
Primary: compound-mini (70K TPM) → Fallback: kimi-k2 (10K TPM) → llama-3.1-8b (6K TPM)
Extraction results are persisted to disk to avoid re-processing on restart.
"""

import asyncio
import json
import logging
import random
import os
import re
from pathlib import Path
from groq import AsyncGroq
from dotenv import load_dotenv
from typing import Any, Dict, List

load_dotenv()
logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent.parent / "data" / "extraction_cache.json"

EXTRACTION_PROMPT = """You are an enterprise-grade financial entity extractor. Extract from this article:
- company_names (ALL companies mentioned — normalise to canonical names, e.g. "Tata Consultancy Services" not "TCS")
- event_types (only from: executive_change/earnings_surprise/rating_action/regulatory_action/debt_restructuring/promoter_activity/fii_dii_flow/commodity_price/policy_change/merger_acquisition/legal_action/market_movement/macro_event)
- sentiment (-1.0 to 1.0, precise)
- sector (MUST pick the best match from: Banking/NBFC/IT/Metals/Energy/Pharma/Auto/FMCG/Infra/Telecom/Technology/Financials/Healthcare/Industrials/Consumer/Utilities/Defence/RealEstate/Other) — use the company's ACTUAL sector, NOT "Other" unless truly unclassifiable
- signal_keywords (high-impact terms from: promoter pledge/CFO resign/auditor resign/going concern/SEBI notice/ED raid/rating downgrade/covenant breach/FII net sell/profit warning/earnings miss/fraud/NPA/write-off/rate hike/tariff/sanctions/layoffs/buyback/stock split/IPO/delisting)
- is_material (bool — true if article reports a concrete financial event, false for opinion/listicle/rates round-up)
- nse_tickers (list of NSE symbols if Indian company, empty list otherwise)

SECTOR RULES:
- Banks → Banking, NBFCs → NBFC, Software/Cloud/SaaS → IT or Technology
- Pharma/Biotech → Pharma or Healthcare, Auto/EV → Auto
- Oil/Gas/Power → Energy, Cement/Construction → Infra
- Gold/Silver/Steel → Metals, Telecom → Telecom
- FMCG/Retail → FMCG or Consumer, Military/Aerospace → Defence
- Real Estate/Housing → RealEstate, Insurance → Financials
- If article is about macro/economy/interest rates and no specific sector: use "Financials"

For is_global_macro=True articles: still extract company_names if any are mentioned.

Return ONLY valid JSON, zero markdown."""

# Model fallback chain — ordered by TPM limit (highest first)
MODEL_CHAIN = [
    "groq/compound-mini",                   # 70K TPM — best for bulk extraction
    "moonshotai/kimi-k2-instruct-0905",     # 10K TPM — solid fallback
    "llama-3.1-8b-instant",                 # 6K TPM — last resort on Groq
]


class ExtractorAgent:

    def __init__(self):
        from utils.groq_pool import get_groq_client
        self.client = get_groq_client()
        self.semaphore = asyncio.Semaphore(2)  # Limits to 2 concurrent Groq calls
        self.extraction_cache = self._load_cache()
        self.current_model_idx = 0  # Start with compound-mini

    def _load_cache(self) -> Dict[str, Any]:
        """Load persistent extraction cache from disk. Invalidates stale 'Other' entries."""
        try:
            if CACHE_PATH.exists():
                with open(CACHE_PATH, "r") as f:
                    data = json.load(f)
                # Invalidate poorly-extracted entries: sector=Other AND no companies
                before = len(data)
                data = {
                    k: v for k, v in data.items()
                    if not (
                        v.get("sector", "Other") == "Other"
                        and not v.get("company_names")
                        and not v.get("signal_keywords")
                    )
                }
                purged = before - len(data)
                if purged > 0:
                    logger.info(f"Invalidated {purged} stale cache entries (Other sector, no entities)")
                logger.info(f"Loaded {len(data)} cached extractions from disk")
                return data
        except Exception as e:
            logger.warning(f"Could not load extraction cache: {e}")
        return {}

    def _save_cache(self):
        """Persist extraction cache to disk."""
        try:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_PATH, "w") as f:
                json.dump(self.extraction_cache, f, default=str)
        except Exception as e:
            logger.warning(f"Could not save extraction cache: {e}")

    @property
    def _current_model(self) -> str:
        return MODEL_CHAIN[min(self.current_model_idx, len(MODEL_CHAIN) - 1)]

    async def _call_with_fallback(self, messages: List[Dict[str, str]]) -> str:
        """Try current model, fallback to next on rate limit."""
        last_error = None
        for model_idx in range(self.current_model_idx, len(MODEL_CHAIN)):
            model = MODEL_CHAIN[model_idx]
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    temperature=0,
                    max_tokens=400,
                    messages=messages,
                )
                # Success — stick with this model
                self.current_model_idx = model_idx
                return response.choices[0].message.content.strip()
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "rate_limit" in error_str or "rate limit" in error_str:
                    # Rotate to backup Groq API key before backoff
                    from utils.groq_pool import rotate_groq_key
                    self.client = rotate_groq_key()
                    delay = min(2 ** model_idx, 4) + random.uniform(0, 0.5)
                    logger.warning(f"Rate limited on {model}, rotated key, retrying in {delay:.1f}s...")
                    last_error = e
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise e

        # All models exhausted — try Gemini as last resort
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                logger.info("All Groq models rate limited, trying Gemini fallback...")
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                combined = "\n".join([m["content"] for m in messages])
                resp = await asyncio.to_thread(
                    lambda: model.generate_content(combined).text
                )
                return resp.strip()
            except Exception as gemini_e:
                logger.error(f"Gemini fallback failed: {gemini_e}")

        # All failed
        raise last_error or Exception("All models rate limited")

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Robustly extract JSON object from LLM response text."""
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strip markdown code fences
        text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Find the largest JSON object using brace matching
        start = text.find('{')
        if start == -1:
            raise json.JSONDecodeError("No JSON object found", text, 0)

        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    return json.loads(candidate)

        # Return partial fallback dict instead of raising (preserves pipeline continuity)
        return {}

    # ── Company → NSE ticker mapping (Nifty50 + key mid-caps) ────
    COMPANY_TICKER_MAP = {
        # Banking
        "hdfc bank": "HDFCBANK", "icici bank": "ICICIBANK", "state bank": "SBIN",
        "sbi": "SBIN", "kotak": "KOTAKBANK", "axis bank": "AXISBANK",
        "indusind": "INDUSINDBK", "bank of baroda": "BANKBARODA", "pnb": "PNB",
        "punjab national": "PNB", "canara bank": "CANBK", "idfc first": "IDFCFIRSTB",
        # IT
        "tata consultancy": "TCS", "tcs": "TCS", "infosys": "INFY",
        "wipro": "WIPRO", "hcl tech": "HCLTECH", "tech mahindra": "TECHM",
        "lt mindtree": "LTIM", "mphasis": "MPHASIS", "coforge": "COFORGE",
        # Energy
        "reliance": "RELIANCE", "ongc": "ONGC", "bpcl": "BPCL", "hpcl": "HPCL",
        "indian oil": "IOC", "gail": "GAIL", "power grid": "POWERGRID",
        "ntpc": "NTPC", "adani green": "ADANIGREEN", "adani power": "ADANIPOWER",
        # Auto
        "maruti": "MARUTI", "tata motors": "TATAMOTORS", "mahindra": "M&M",
        "m&m": "M&M", "bajaj auto": "BAJAJ-AUTO", "hero moto": "HEROMOTOCO",
        "eicher": "EICHERMOT", "ashok leyland": "ASHOKLEY", "tvs motor": "TVSMOTOR",
        # Metals
        "tata steel": "TATASTEEL", "hindalco": "HINDALCO", "jsw steel": "JSWSTEEL",
        "vedanta": "VEDL", "coal india": "COALINDIA", "nmdc": "NMDC", "sail": "SAIL",
        # Pharma
        "sun pharma": "SUNPHARMA", "dr reddy": "DRREDDY", "cipla": "CIPLA",
        "divi's": "DIVISLAB", "divis": "DIVISLAB", "apollo hosp": "APOLLOHOSP",
        "lupin": "LUPIN", "aurobindo": "AUROPHARMA", "biocon": "BIOCON",
        # FMCG
        "hindustan unilever": "HINDUNILVR", "hul": "HINDUNILVR", "itc": "ITC",
        "nestle": "NESTLEIND", "britannia": "BRITANNIA", "dabur": "DABUR",
        "marico": "MARICO", "godrej consumer": "GODREJCP", "colgate": "COLPAL",
        # Infra / Conglomerate
        "larsen": "LT", "l&t": "LT", "adani enterprise": "ADANIENT",
        "adani ports": "ADANIPORTS", "ultratech": "ULTRACEMCO", "grasim": "GRASIM",
        "dlf": "DLF", "acc": "ACC", "ambuja": "AMBUJACEM",
        # NBFC / Financial
        "bajaj finance": "BAJFINANCE", "bajaj finserv": "BAJAJFINSV",
        "sbi life": "SBILIFE", "hdfc life": "HDFCLIFE", "muthoot": "MUTHOOTFIN",
        "cholamandalam": "CHOLAFIN", "shriram": "SHRIRAMFIN",
        # Telecom
        "bharti airtel": "BHARTIARTL", "airtel": "BHARTIARTL",
        "vodafone idea": "IDEA", "jio": "RELIANCE",
        # Others
        "asian paints": "ASIANPAINT", "titan": "TITAN", "pidilite": "PIDILITIND",
        "havells": "HAVELLS", "siemens": "SIEMENS", "abb": "ABB",
        "zomato": "ZOMATO", "paytm": "PAYTM", "policybazaar": "POLICYBZR",
        "nykaa": "NYKAA", "delhivery": "DELHIVERY",
        "flipkart": "FLIPKART", "swiggy": "SWIGGY",
    }

    def _map_company_to_tickers(self, company_names: list, title: str = "") -> list[str]:
        """Map extracted company names to NSE ticker symbols."""
        tickers = set()
        search_text = " ".join(company_names).lower() + " " + title.lower()
        
        for name_pattern, ticker in self.COMPANY_TICKER_MAP.items():
            if name_pattern in search_text:
                tickers.add(ticker)
        
        return list(tickers)[:5]  # Cap at 5 tickers per signal

    async def _extract_one(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Extract entities from a single article."""
        # Use article ID as cache key (more reliable than URL which may be missing)
        cache_key = article.get("url", "") or article.get("id", "")
        if cache_key and cache_key in self.extraction_cache:
            return self.extraction_cache[cache_key]

        async with self.semaphore:
            try:
                is_macro = article.get("is_global_macro", False)
                content = f"Title: {article.get('title', '')}\nDescription: {article.get('description', '')}\nSource: {article.get('source_channel', '')}\nis_global_macro: {is_macro}"

                text = await self._call_with_fallback([
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user", "content": content},
                ])

                extraction = self._extract_json(text)
                extraction["article_id"] = article.get("id", "")
                extraction["source_channel"] = article.get("source_channel", "")
                extraction["published_at"] = article.get("published_at", "")

                # Auto-map company names to NSE tickers if LLM didn't provide them
                if not extraction.get("nse_tickers"):
                    extraction["nse_tickers"] = self._map_company_to_tickers(
                        extraction.get("company_names", []),
                        article.get("title", ""),
                    )

                if cache_key:
                    self.extraction_cache[cache_key] = extraction

                # Throttle: small delay between successful calls to stay under TPM
                await asyncio.sleep(1)

                return extraction

            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error for {article.get('title', '')}: {e}")
                return {
                    "article_id": article.get("id", ""),
                    "company_names": [],
                    "event_types": [],
                    "sentiment": 0.0,
                    "sector": "Other",
                    "signal_keywords": [],
                    "is_material": False,
                    "nse_tickers": [],
                    "error": str(e),
                }
            except Exception as e:
                logger.error(f"Extraction error for {article.get('title', '')}: {e}")
                return {
                    "article_id": article.get("id", ""),
                    "company_names": [],
                    "event_types": [],
                    "sentiment": 0.0,
                    "sector": "Other",
                    "signal_keywords": [],
                    "is_material": False,
                    "nse_tickers": [],
                    "error": str(e),
                }

    async def extract_batch(self, articles: List[Any]) -> List[Dict[str, Any]]:
        """Extract entities from a batch of articles."""
        if not articles:
            return []

        # Convert Pydantic models to dicts if needed
        article_dicts: List[Dict[str, Any]] = []
        for a in articles:
            model_dump = getattr(a, "model_dump", None)
            if callable(model_dump):
                article_dicts.append(model_dump())
            elif isinstance(a, dict):
                article_dicts.append(a)
            else:
                article_dicts.append(dict(a))

        # Separate cached vs uncached articles
        cached_results: List[Dict[str, Any]] = []
        uncached_articles: List[Dict[str, Any]] = []
        for a in article_dicts:
            cache_key = a.get("url", "") or a.get("id", "")
            if cache_key and cache_key in self.extraction_cache:
                cached_results.append(self.extraction_cache[cache_key])
            else:
                uncached_articles.append(a)

        # Cap uncached to 50 most recent to stay within rate limits
        if len(uncached_articles) > 50:
            logger.info(f"Capping extraction from {len(uncached_articles)} to 50 most recent articles")
            # Sort by published_at descending to ensure newest articles are processed first
            uncached_articles.sort(
                key=lambda a: a.get("published_at", ""),
                reverse=True
            )
            uncached_articles = uncached_articles[:50]

        logger.info(f"Extraction batch: {len(cached_results)} cached, {len(uncached_articles)} need LLM processing")

        # Reset to best model at start of batch
        self.current_model_idx = 0

        # Process uncached articles in PARALLEL using semaphore for rate limiting
        new_extractions: List[Dict[str, Any]] = []
        if uncached_articles:
            async def _safe_extract(article: Dict[str, Any]) -> Dict[str, Any]:
                try:
                    return await self._extract_one(article)
                except Exception as e:
                    logger.error(f"Extraction exception: {e}")
                    return {
                        "company_names": [],
                        "event_types": [],
                        "sentiment": 0.0,
                        "sector": "Other",
                        "signal_keywords": [],
                        "is_material": False,
                        "nse_tickers": [],
                        "error": str(e),
                    }

            # Run all extractions concurrently — semaphore limits to 3 at a time
            new_extractions = list(await asyncio.gather(
                *[_safe_extract(a) for a in uncached_articles]
            ))
            logger.info(f"Parallel extraction complete: {len(new_extractions)} articles processed")

            # Persist cache to disk after batch completes
            self._save_cache()

        all_extractions = cached_results + new_extractions
        material = sum(1 for e in all_extractions if e.get('is_material'))
        logger.info(f"Extracted {len(all_extractions)} articles ({len(cached_results)} from cache), {material} material")
        return all_extractions
