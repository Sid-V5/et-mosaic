# pyre-ignore-all-errors
"""
Mosaic Builder Agent — core intelligence agent.
Finds cross-source connections using cosine similarity + market verification + LLM pattern classification.
Enterprise-grade: all numpy types converted to Python natives, robust error handling, no deprecated APIs.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np  # type: ignore[import-untyped]
from scipy.spatial.distance import cdist  # type: ignore[import-untyped]
from groq import AsyncGroq  # type: ignore[import-untyped]
from dotenv import load_dotenv  # type: ignore[import-untyped]

load_dotenv()
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

MOSAIC_PROMPT = (
    "You are the Mosaic Builder practising Mosaic Theory. Given these articles, "
    "market data, and technical indicators: does this constitute a real financial signal? "
    "Classify the pattern from: TRIPLE_THREAT/GOVERNANCE_DETERIORATION/REGULATORY_CONVERGENCE"
    "/SILENT_ACCUMULATION/SENTIMENT_VELOCITY. Return JSON: {is_signal, confidence 0-100, "
    "signal_type, explanation (2 sentences citing specific evidence), severity low/medium/high}."
)

# Model fallback chain — ordered by TPM limit
MOSAIC_MODEL_CHAIN = [
    "groq/compound-mini",                   # 70K TPM
    "moonshotai/kimi-k2-instruct-0905",     # 10K TPM
    "llama-3.3-70b-versatile",              # original
]


class MosaicBuilderAgent:

    def __init__(
        self,
        chroma_store: Any = None,
        ta_service: Any = None,
    ) -> None:
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.chroma_store = chroma_store
        self.ta_service = ta_service
        self.accuracy_data = self._load_accuracy()

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _load_accuracy() -> dict:
        try:
            with open(os.path.join(DATA_DIR, "accuracy_store.json"), "r") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def _to_python_list(val: Any) -> list:
        """Safely convert any value to a flat list of strings, to avoid unhashable type errors in sets."""
        if val is None:
            return []
        
        if hasattr(val, "tolist"):
            val = val.tolist()
            
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    val = parsed
            except Exception:
                pass
                
        if isinstance(val, (list, tuple)):
            # Flatten and safely convert to string to ensure hashability
            flat = []
            for item in val:
                if isinstance(item, (list, tuple)):
                    flat.extend([str(x) for x in item])
                elif isinstance(item, dict):
                    pass # ignore complex dicts in keywords/companies
                elif item is not None:
                    flat.append(str(item))
            return flat
            
        if val:
            return [str(val)]
        return []

    @staticmethod
    def _safe_first(lst: Any, default: str = "") -> str:
        """Return first element of list-like safely, or default."""
        py_list = MosaicBuilderAgent._to_python_list(lst)
        return str(py_list[0]) if py_list else default

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Robustly extract JSON object from LLM response text using brace matching."""
        # Strip markdown fences
        text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Brace-matching fallback
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
                    return json.loads(text[start:i + 1])  # type: ignore[index]

        raise json.JSONDecodeError("Incomplete JSON object", text, 0)

    # ── async TA fallback ────────────────────────────────────────

    @staticmethod
    async def _empty_dict() -> dict:
        """Async no-op returning empty dict — replaces deprecated asyncio.coroutine."""
        return {}

    # ── main entry point ─────────────────────────────────────────

    async def find_connections(self, extractions: list) -> list[dict]:
        """Find cross-source connections from extracted article data."""
        try:
            return await self._find_connections_impl(extractions)
        except Exception:
            err_trace = traceback.format_exc()
            logger.error(f"Mosaic find_connections error:\n{err_trace}")
            with open("mosaic_traceback.txt", "w") as f:
                f.write(err_trace)
            raise

    async def _find_connections_impl(self, extractions: list) -> list[dict]:
        if not extractions or len(extractions) < 2:
            logger.warning(f"Mosaic: insufficient extractions ({len(extractions) if extractions else 0}), need >= 2")
            return []

        from tools.nse_tools import fetch_bulk_deals, fetch_price_volume  # type: ignore[import-untyped]

        # ── 1. Load articles from ChromaDB ───────────────────────
        all_articles: list[dict] = []
        embeddings_matrix: list[list[float]] = []

        if self.chroma_store:
            stored = self.chroma_store.get_recent_articles(days=7)
            if stored and stored.get("ids"):
                metas = stored.get("metadatas")
                embs = stored.get("embeddings")
                for i, aid in enumerate(stored["ids"]):
                    meta = metas[i] if metas is not None else {}  # type: ignore[index]
                    emb = embs[i] if embs is not None else None  # type: ignore[index]
                    if emb is not None:
                        raw_sector = meta.get("sector", "Other")
                        title = meta.get("title", "")
                        all_articles.append({
                            "id": aid,
                            "title": title,
                            "source_channel": meta.get("source_channel", ""),
                            "url": meta.get("url", ""),
                            "sector": self._infer_sector(title, "", raw_sector),
                            "sentiment": float(meta.get("sentiment") or 0),
                            "published_at": meta.get("published_at", ""),
                            "nse_tickers": json.loads(meta.get("nse_tickers", "[]")) if meta.get("nse_tickers") else [],
                            "signal_keywords": json.loads(meta.get("signal_keywords", "[]")) if meta.get("signal_keywords") else [],
                        })
                        # Ensure embedding is plain Python list
                        embeddings_matrix.append(
                            emb.tolist() if hasattr(emb, "tolist") else list(emb)
                        )

        logger.info(f"Mosaic: loaded {len(all_articles)} articles with embeddings from ChromaDB (chroma_store={self.chroma_store is not None})")

        # ── 2. Merge extraction data ─────────────────────────────
        extraction_map = {e.get("article_id", ""): e for e in extractions if e.get("article_id")}
        for article in all_articles:
            ext = extraction_map.get(article["id"])
            if ext:
                article["company_names"] = ext.get("company_names", [])
                article["event_types"] = ext.get("event_types", [])
                article["signal_keywords"] = ext.get("signal_keywords", article.get("signal_keywords", []))
                article["sentiment"] = float(ext.get("sentiment") or article.get("sentiment") or 0)
                ext_sector = ext.get("sector", article.get("sector", "Other"))
                article["sector"] = self._infer_sector(article.get("title", ""), "", ext_sector)
                article["nse_tickers"] = ext.get("nse_tickers", article.get("nse_tickers", []))

        if len(embeddings_matrix) < 2:
            logger.warning(f"Mosaic: only {len(embeddings_matrix)} embeddings, need >= 2")
            return []

        # ── 3. Cosine similarity matrix ──────────────────────────
        emb_array = np.array(embeddings_matrix)
        sim_matrix = 1 - cdist(emb_array, emb_array, metric="cosine")

        # ── 4. Find candidate pairs ──────────────────────────────
        candidates: list[dict] = []
        # CRITICAL: n must be capped at sim_matrix size to prevent index-out-of-bounds
        n = min(len(all_articles), len(sim_matrix))
        to_list = self._to_python_list  # local reference — avoids method lookup in O(n²) loop

        for i in range(n):
            for j in range(i + 1, n):
                sim = float(sim_matrix[i][j])  # type: ignore[index]
                if not (0.15 < sim < 0.95):
                    continue

                a1, a2 = all_articles[i], all_articles[j]  # type: ignore[index]
                if str(a1.get("source_channel", "")) == str(a2.get("source_channel", "")):
                    continue

                c1 = to_list(a1.get("company_names", []))
                c2 = to_list(a2.get("company_names", []))
                k1 = to_list(a1.get("signal_keywords", []))
                k2 = to_list(a2.get("signal_keywords", []))

                shared_companies = set(c1) & set(c2)
                both_keywords = len(k1) > 0 and len(k2) > 0
                same_sector = (
                    a1.get("sector", "Other") == a2.get("sector", "Other")
                    and a1.get("sector", "Other") != "Other"
                )

                if not shared_companies and not both_keywords and not same_sector:
                    continue

                t1 = to_list(a1.get("nse_tickers", []))
                t2 = to_list(a2.get("nse_tickers", []))
                candidates.append({
                    "articles": [a1, a2],
                    "similarity": sim,
                    "shared_companies": list(shared_companies),
                    "shared_tickers": list(set(t1) & set(t2)),
                })

        if not candidates:
            logger.warning(f"Mosaic: 0 candidates after filtering {n} articles")
            return []

        # ── 5. Score and verify candidates in parallel ──────────────
        async def _safe_score(c: dict) -> Optional[dict]:
            try:
                return await self._score_candidate(c, fetch_bulk_deals, fetch_price_volume)
            except Exception as e:
                logger.error(f"Connection processing error: {e}")
                return None

        scored = await asyncio.gather(*[_safe_score(c) for c in candidates[:30]])  # type: ignore[index]
        connections = [c for c in scored if c is not None]

        # ── 6. Write graph_data.json for D3 frontend ─────────────
        self._write_graph_data(connections, all_articles)

        logger.info(f"Found {len(connections)} validated connections from {len(candidates)} candidates")
        return connections

    # ── candidate scoring ────────────────────────────────────────

    async def _score_candidate(
        self,
        cand: dict,
        fetch_bulk_deals,
        fetch_price_volume,
    ) -> Optional[dict]:
        """Score a single candidate pair. Returns a connection dict or None."""

        company = self._safe_first(
            cand["shared_companies"]
            or cand["articles"][0].get("company_names", []),
            default="Unknown",
        )
        ticker = self._safe_first(
            cand["shared_tickers"]
            or cand["articles"][0].get("nse_tickers", []),
            default="",
        )

        # ── parallel market data fetches ─────────────────────────
        if ticker:
            ta_coro = self.ta_service.analyse(ticker) if self.ta_service else self._empty_dict()
            market_results = await asyncio.gather(
                fetch_bulk_deals(company),
                fetch_price_volume([ticker]),
                ta_coro,
                return_exceptions=True,
            )
            bulk_deals = market_results[0] if not isinstance(market_results[0], Exception) else []
            price_data = market_results[1] if not isinstance(market_results[1], Exception) else {}
            ta_data = market_results[2] if not isinstance(market_results[2], Exception) else {}
        else:
            bulk_deals, price_data, ta_data = [], {}, {}

        # ── composite score ──────────────────────────────────────
        shared_entity_score = min(len(cand["shared_companies"]) * 25, 50)
        market_confirmation = 0
        if bulk_deals:
            market_confirmation += 30
        if isinstance(price_data, dict) and price_data.get(ticker, {}).get("volume_spike"):
            market_confirmation += 20
        if isinstance(ta_data, dict) and ta_data.get("confirms_risk"):
            market_confirmation += 30

        pattern_score = len(self._to_python_list(cand["articles"][0].get("signal_keywords", []))) * 10  # type: ignore[index]

        # Sector overlap bonus
        sector_a1 = cand["articles"][0].get("sector", "Other")  # type: ignore[index]
        sector_a2 = cand["articles"][1].get("sector", "Other")  # type: ignore[index]
        sector_overlap = 20 if (sector_a1 == sector_a2 and sector_a1 != "Other") else 0

        base = (
            cand["similarity"] * 0.35
            + (shared_entity_score / 100) * 0.20
            + (market_confirmation / 100) * 0.15
            + min(pattern_score / 100, 1.0) * 0.10
            + (sector_overlap / 100) * 0.20
        ) * 100

        # Temporal decay
        try:
            published_dates = [
                datetime.fromisoformat(a.get("published_at", "").replace("Z", "+00:00"))
                for a in cand["articles"] if a.get("published_at")
            ]
            if published_dates:
                days_old = (datetime.now(timezone.utc) - min(published_dates)).days
            else:
                days_old = 1
        except Exception:
            days_old = 1
        base *= 0.96 ** days_old

        # Accuracy weight
        signal_type_guess = "TRIPLE_THREAT"
        acc = self.accuracy_data.get(signal_type_guess, {}).get("accuracy", 50) / 100
        base *= 0.5 + acc * 0.5

        if base < 15:
            return None

        # ── LLM verification ─────────────────────────────────────
        evidence = json.dumps({
            "articles": [
                {"title": a["title"], "source": a["source_channel"], "sentiment": float(a.get("sentiment", 0))}
                for a in cand["articles"]
            ],
            "bulk_deals": (bulk_deals[:5] if isinstance(bulk_deals, list) else []),  # type: ignore[index]
            "price_data": (price_data.get(ticker, {}) if isinstance(price_data, dict) else {}),
            "technical": (ta_data if isinstance(ta_data, dict) else {}),
            "similarity": cand["similarity"],
        }, default=str)

        llm_result = await self._llm_verify(evidence, base)

        if not llm_result.get("is_signal", False):
            return None

        # Resolve sector from articles
        a1_sector = cand["articles"][0].get("sector", "Other")  # type: ignore[index]
        a2_sector = cand["articles"][1].get("sector", "Other")  # type: ignore[index]
        resolved_sector = a1_sector if a1_sector != "Other" else a2_sector

        # Collect event types from both articles
        all_events = list(set(
            self._to_python_list(cand["articles"][0].get("event_types", []))  # type: ignore[index]
            + self._to_python_list(cand["articles"][1].get("event_types", []))  # type: ignore[index]
        ))

        # Better company resolution: use extracted companies, keywords, or title tokens
        resolved_companies = cand["shared_companies"] or [company]
        if resolved_companies == ["Unknown"]:
            # Try to extract a company name from article titles
            for a in cand["articles"]:
                names = self._to_python_list(a.get("company_names", []))
                if names:
                    resolved_companies = names[:3]
                    break

        # ── build connection dict (all native Python types) ──────
        return {
            "article_ids": [a["id"] for a in cand["articles"]],
            "company_names": resolved_companies,
            "nse_tickers": cand["shared_tickers"] or ([ticker] if ticker else []),
            "sector": resolved_sector,
            "event_types": all_events[:5],
            "signal_type": str(llm_result.get("signal_type", "TRIPLE_THREAT")),
            "pattern_matched": str(llm_result.get("signal_type", "TRIPLE_THREAT")),
            "confidence": int(llm_result.get("confidence", int(base))),
            "severity": str(llm_result.get("severity", "medium")),
            "explanation": str(llm_result.get("explanation", "")),
            "market_data_confirmation": round(float(int(market_confirmation)) / 100.0, 2),  # type: ignore[call-overload]
            "historical_match": round(float(acc), 2),  # type: ignore[call-overload]
            "sentiment_velocity": float(int(
                abs(float(cand["articles"][0].get("sentiment", 0))
                    - float(cand["articles"][1].get("sentiment", 0))) * 10000
            )) / 10000.0,
            "similarity": round(float(cand.get("similarity", 0.0)), 3),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sources": [
                {"title": a["title"], "source": a["source_channel"], "url": a.get("url", "")}
                for a in cand["articles"]
            ],
            "bulk_deals": (bulk_deals[:5] if isinstance(bulk_deals, list) else []),  # type: ignore[index]
            "price_data": (price_data.get(ticker, {}) if isinstance(price_data, dict) else {}),
            "technical": (ta_data if isinstance(ta_data, dict) else {}),
        }

    # ── LLM call with fallback chain ─────────────────────────────

    async def _llm_verify(self, evidence: str, base_score: float) -> dict:
        """Call Groq with model fallback to verify a candidate connection."""
        for model_name in MOSAIC_MODEL_CHAIN:
            try:
                response = await self.client.chat.completions.create(
                    model=model_name,
                    temperature=0.1,
                    max_tokens=1024, # Increased to prevent JSON cutoffs
                    messages=[
                        {"role": "system", "content": MOSAIC_PROMPT},
                        {"role": "user", "content": evidence},
                    ],
                )
                text = response.choices[0].message.content.strip()
                return self._extract_json(text)
            except Exception as model_e:
                # Instead of breaking on non-rate-limit errors (like JSON parsing fails), 
                # we should continue testing the fallback model chain.
                logger.warning(f"Mosaic: Model evaluation failed on {model_name} with error: {model_e}. Trying next...")
                await asyncio.sleep(2)
                continue

        # Fallback: assume signal with base score
        return {
            "is_signal": True,
            "confidence": int(base_score),
            "signal_type": "TRIPLE_THREAT",
            "explanation": "Cross-source convergence detected.",
            "severity": "medium",
        }

    # ── Keyword-based sector inference ──────────────────────────

    SECTOR_KEYWORDS: dict[str, list[str]] = {
        "Metals": ["silver", "gold", "steel", "copper", "zinc", "aluminium", "aluminum", "iron ore", "nickel", "palladium", "platinum", "lme", "vedanta", "hindalco", "tata steel", "jsw steel", "hindustan zinc", "nmdc", "coal india", "metal", "mining"],
        "Energy": ["oil", "gas", "crude", "brent", "opec", "petroleum", "reliance", "ongc", "ioc", "bpcl", "hpcl", "gail", "power", "solar", "wind", "coal", "adani green", "ntpc", "power grid", "energy"],
        "Banking": ["bank", "rbi", "repo rate", "npa", "credit growth", "deposit", "hdfc", "icici", "sbi", "kotak", "axis bank", "pnb", "bob", "canara", "loan", "lending", "interest rate", "banking"],
        "IT": ["software", "infosys", "tcs", "wipro", "hcl tech", "tech mahindra", "cognizant", "outsourcing", "saas", "cloud computing", "ai ", "artificial intelligence", "digital", "cybersecurity"],
        "Pharma": ["pharma", "drug", "fda", "clinical trial", "biotech", "sun pharma", "cipla", "dr reddy", "lupin", "divis", "aurobindo", "api ", "generic", "medicine", "hospital"],
        "Auto": ["auto", "automobile", "car", "ev ", "electric vehicle", "maruti", "tata motors", "mahindra", "bajaj auto", "hero moto", "eicher", "two-wheeler", "passenger vehicle", "commercial vehicle"],
        "FMCG": ["fmcg", "consumer goods", "hindustan unilever", "itc ", "nestle", "britannia", "dabur", "marico", "godrej consumer", "colgate", "soap", "shampoo", "food"],
        "Telecom": ["telecom", "jio", "airtel", "vodafone", "idea", "5g", "spectrum", "trai", "mobile", "broadband", "bharti"],
        "Financials": ["insurance", "mutual fund", "amc", "nbfc", "bajaj finance", "shriram", "muthoot", "manappuram", "lic ", "policy", "premium", "ipo ", "stock market", "sensex", "nifty", "equity", "bond", "yield", "fii ", "dii ", "fund flow", "gdp", "inflation", "fiscal", "budget", "gst", "tax"],
        "Infra": ["infrastructure", "cement", "construction", "real estate", "highway", "road", "bridge", "port", "railway", "metro", "ultratech", "ambuja", "acc cement", "larsen", "engineering"],
        "Technology": ["startup", "fintech", "edtech", "ecommerce", "e-commerce", "zomato", "swiggy", "paytm", "razorpay", "unicorn", "vc ", "venture capital", "funding round"],
        "Healthcare": ["healthcare", "hospital", "apollo", "fortis", "max health", "medanta", "diagnostic", "path lab", "wellness"],
        "Defence": ["defence", "defense", "military", "hal ", "bharat dynamics", "bharat electronics", "missile", "ammunition", "army", "navy", "air force"],
        "Consumer": ["retail", "fashion", "apparel", "luxury", "titan", "trent", "avenue supermarts", "dmart", "shoppers stop", "lifestyle"],
    }

    @classmethod
    def _infer_sector(cls, title: str, description: str = "", current_sector: Any = "Other") -> str:
        """Infer sector from article text when LLM returned 'Other'."""
        # LLM might occasionally return a list like ["Metals"]
        if isinstance(current_sector, list) and current_sector:
            current_sector = str(current_sector[0])
        elif not isinstance(current_sector, str):
            current_sector = str(current_sector) if current_sector else "Other"
            
        # Catch LLM hallucinations that generate whole sentences as sectors
        if len(current_sector) > 25:
            current_sector = "Other"
            
        if current_sector != "Other":
            return current_sector
        text = (title + " " + description).lower()
        best_sector = "Other"
        best_score = 0
        for sector, keywords in cls.SECTOR_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_sector = sector
        return best_sector if best_score > 0 else "Other"

    # ── D3 graph data writer ─────────────────────────────────────

    def _write_graph_data(self, connections: list, articles: list) -> None:
        """Write a meaningful, connected graph for the D3 frontend.

        Strategy:
        - Infer missing sectors from article titles
        - Create sector hub nodes + company hub nodes
        - Connect articles → sector hubs, articles → company hubs
        - Add signal edges from MosaicBuilder connections
        - Drop orphan nodes (no edges) to keep graph clean
        - Cap at ~120 most-connected nodes for performance
        """
        from collections import defaultdict

        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        edge_set: set[tuple[str, str]] = set()

        def _add_edge(src: str, tgt: str, severity: str = "low",
                      confidence: int = 30, label: str = "") -> bool:
            key = (min(src, tgt), max(src, tgt))
            if key in edge_set or src not in nodes or tgt not in nodes:
                return False
            edge_set.add(key)
            edges.append({
                "source": src, "target": tgt,
                "severity": severity, "confidence": confidence, "label": label,
            })
            nodes[src]["connections_count"] += 1
            nodes[tgt]["connections_count"] += 1
            return True

        # ── Step 1: Build article nodes with inferred sectors ────
        for article in articles:
            nid = article["id"]
            raw_sector = article.get("sector") or "Other"
            inferred = self._infer_sector(
                article.get("title", ""),
                article.get("description", "") if isinstance(article.get("description"), str) else "",
                raw_sector,
            )
            article["sector"] = inferred  # update in-place for downstream

            nodes[nid] = {
                "id": nid,
                "label": article.get("title", "")[:60],
                "type": "article",
                "sector": inferred,
                "confidence": 0,
                "connections_count": 0,
                "metadata": {
                    "title": article.get("title", ""),
                    "source": article.get("source_channel", ""),
                    "published_at": article.get("published_at", ""),
                },
            }

        # ── Step 2: Create sector hub nodes ──────────────────────
        sector_groups: dict[str, list[str]] = defaultdict(list)
        for article in articles:
            sector = article.get("sector", "Other")
            if sector != "Other":
                sector_groups[sector].append(article["id"])

        for sector, aids in sector_groups.items():
            if len(aids) < 1:
                continue
            sid = f"sector_{sector.lower()}"
            nodes[sid] = {
                "id": sid,
                "label": sector,
                "type": "sector",
                "sector": sector,
                "confidence": 30,
                "connections_count": 0,
                "metadata": {"signal_type": "sector_hub"},
            }
            for aid in aids[:20]:  # cap connections per sector hub
                _add_edge(aid, sid, "low", 25, "sector")

        # ── Step 3: Company hub nodes ────────────────────────────
        company_groups: dict[str, list[str]] = defaultdict(list)
        for article in articles:
            for company in self._to_python_list(article.get("company_names", [])):
                if company and len(company) > 1:
                    company_groups[company.lower().strip()].append(article["id"])

        for company_name, aids in company_groups.items():
            if len(aids) < 2:
                continue
            cid = f"company_{company_name.replace(' ', '_')}"
            # Find the sector of the company from articles
            comp_sector = "Other"
            for aid in aids:
                if aid in nodes and nodes[aid].get("sector", "Other") != "Other":
                    comp_sector = nodes[aid]["sector"]
                    break
            nodes[cid] = {
                "id": cid,
                "label": company_name.title(),
                "type": "company",
                "sector": comp_sector,
                "confidence": 50,
                "connections_count": 0,
                "metadata": {"signal_type": "entity_hub"},
            }
            for aid in aids[:12]:
                _add_edge(aid, cid, "low", 40, "entity")
            # Also connect company to its sector hub
            sec_hub = f"sector_{comp_sector.lower()}"
            if sec_hub in nodes:
                _add_edge(cid, sec_hub, "low", 35, "company_sector")

        # ── Step 4: Signal edges from Mosaic connections ─────────
        for conn in connections:
            conf = conn.get("confidence", 0)
            sev = conn.get("severity", "medium")
            sig_type = conn.get("signal_type", "")

            # Connect article pairs
            article_ids = conn.get("article_ids", [])
            for i, aid1 in enumerate(article_ids):
                for aid2 in article_ids[i + 1:]:
                    _add_edge(aid1, aid2, sev, conf, sig_type)

            # Connect to company nodes
            for company in conn.get("company_names", []):
                cid = f"company_{company.lower().replace(' ', '_')}"
                if cid not in nodes:
                    nodes[cid] = {
                        "id": cid,
                        "label": company,
                        "type": "company",
                        "sector": conn.get("sector", "Other"),
                        "confidence": conf,
                        "connections_count": 0,
                        "metadata": {"signal_type": sig_type},
                    }
                for aid in article_ids:
                    _add_edge(aid, cid, sev, conf, sig_type)

        # ── Step 5: Keyword-based inter-article edges ────────────
        # Connect articles that share signal_keywords
        keyword_groups: dict[str, list[str]] = defaultdict(list)
        for article in articles:
            for kw in self._to_python_list(article.get("signal_keywords", [])):
                if kw and len(str(kw)) > 2:
                    keyword_groups[str(kw).lower()].append(article["id"])

        for kw, aids in keyword_groups.items():
            if len(aids) < 2:
                continue
            for i, a1 in enumerate(aids[:8]):
                for a2 in aids[i + 1:8]:
                    _add_edge(a1, a2, "medium", 45, f"keyword:{kw[:20]}")

        # ── Step 6: Drop orphan nodes ────────────────────────────
        connected_ids = {n_id for n_id, n in nodes.items() if n["connections_count"] > 0}
        nodes = {n_id: n for n_id, n in nodes.items() if n_id in connected_ids}

        # ── Step 7: Cap node count — keep most connected ─────────
        MAX_NODES = 120
        if len(nodes) > MAX_NODES:
            # Always keep sector/company hubs; sort articles by connections
            hubs = {k: v for k, v in nodes.items() if v["type"] in ("sector", "company")}
            articles_sorted = sorted(
                [(k, v) for k, v in nodes.items() if v["type"] == "article"],
                key=lambda x: x[1]["connections_count"],
                reverse=True,
            )
            remaining = MAX_NODES - len(hubs)
            keep_ids = set(hubs.keys()) | {k for k, _ in articles_sorted[:remaining]}
            nodes = {k: v for k, v in nodes.items() if k in keep_ids}
            # Filter edges to only include kept nodes
            edges = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
            # Recount connections
            for n in nodes.values():
                n["connections_count"] = 0
            for e in edges:
                if e["source"] in nodes:
                    nodes[e["source"]]["connections_count"] += 1
                if e["target"] in nodes:
                    nodes[e["target"]]["connections_count"] += 1

        graph_data = {"nodes": list(nodes.values()), "edges": edges}

        try:
            with open(os.path.join(DATA_DIR, "graph_data.json"), "w") as f:
                json.dump(graph_data, f, indent=2, default=str)
            logger.info(f"Graph data written: {len(nodes)} nodes, {len(edges)} edges")
        except Exception as e:
            logger.error(f"Error writing graph_data.json: {e}")

