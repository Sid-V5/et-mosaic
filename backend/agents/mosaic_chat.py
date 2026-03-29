# pyre-ignore-all-errors
"""
Mosaic Chat Agent -- answers user queries using graph data, signals,
accuracy history, and user portfolio. Uses Groq LLaMA for reasoning.
"""

import json
import os
import logging
from datetime import datetime
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

SYSTEM_PROMPT = """You are the ET Mosaic intelligence agent. You have access to a live knowledge graph
built from Economic Times articles, NSE bulk deal data, and technical indicators for the Indian market.

Your role:
- Answer questions about connections, signals, risks, and convergence patterns in the data
- Be specific: cite article titles, confidence scores, company names, signal types, and dates
- If multiple signals exist, rank them by confidence and severity
- When the user asks about their portfolio, cross-reference their holdings against active signals
- If the data doesn't fully answer the question, say what you DO know and what's missing
- Keep answers concise (4-6 sentences) and data-driven
- Use financial terminology naturally (not ML jargon like cosine, embedding, etc.)
- NEVER give investment advice. End every response with: For research only.

You have access to:
1. Active signals with confidence scores, severity levels, and source articles
2. Knowledge graph showing company connections and sector relationships
3. Historical accuracy data showing how well past predictions performed
4. The user's portfolio holdings (if provided)
"""


class MosaicChat:

    def __init__(self):
        from utils.groq_pool import get_groq_client
        self.client = get_groq_client()

    def _load_context(self, portfolio: list = None) -> dict:
        """Load current graph data, signals, and accuracy."""
        context = {"signals": [], "graph_summary": {}, "accuracy": {}, "portfolio": portfolio or []}

        # Load signals
        try:
            signals_path = os.path.join(DATA_DIR, "signals.json")
            if os.path.exists(signals_path):
                with open(signals_path) as f:
                    context["signals"] = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load signals: {e}")

        # Load graph
        try:
            graph_path = os.path.join(DATA_DIR, "graph_data.json")
            if os.path.exists(graph_path):
                with open(graph_path) as f:
                    graph = json.load(f)
                    nodes = graph.get("nodes", [])
                    edges = graph.get("edges", [])
                    
                    # Sector breakdown
                    sectors = {}
                    for n in nodes:
                        s = n.get("sector", "Other")
                        sectors[s] = sectors.get(s, 0) + 1
                    
                    # High severity edges with details
                    high_edges = [
                        f"{e.get('source_label', e.get('source','?'))} <-> {e.get('target_label', e.get('target','?'))} ({e.get('label', '')})"
                        for e in edges if e.get("severity") == "high"
                    ][:15]
                    
                    context["graph_summary"] = {
                        "total_nodes": len(nodes),
                        "total_edges": len(edges),
                        "sectors": sectors,
                        "high_severity_edges": high_edges,
                        "companies": [
                            n.get("label") for n in nodes
                            if n.get("type") == "company"
                        ][:30],
                    }
        except Exception as e:
            logger.warning(f"Could not load graph: {e}")

        # Load accuracy data
        try:
            accuracy_path = os.path.join(DATA_DIR, "accuracy_store.json")
            if os.path.exists(accuracy_path):
                with open(accuracy_path) as f:
                    acc_data = json.load(f)
                    total = len(acc_data)
                    correct = sum(1 for v in acc_data.values() if v.get("outcome") == "correct")
                    context["accuracy"] = {
                        "total_tracked": total,
                        "correct": correct,
                        "accuracy_pct": round(correct / total * 100, 1) if total > 0 else 0,
                        "recent": list(acc_data.values())[-5:] if acc_data else [],
                    }
        except Exception:
            pass

        return context

    async def answer(self, query: str, signal_id: str = None, portfolio: list = None) -> dict:
        """Answer a user query using current pipeline data."""
        context = self._load_context(portfolio)

        # Build structured context string
        parts = []
        
        # Graph summary (placed first -- most important broad context)
        gs = context.get("graph_summary", {})
        if gs:
            sector_str = ", ".join(f"{k}: {v}" for k, v in gs.get("sectors", {}).items())
            parts.append(
                f"KNOWLEDGE GRAPH: {gs.get('total_nodes', 0)} entities, {gs.get('total_edges', 0)} connections.\n"
                f"Sector breakdown: {sector_str}\n"
                f"Key companies tracked: {', '.join(gs.get('companies', []))}"
            )
            if gs.get("high_severity_edges"):
                parts.append(f"HIGH-SEVERITY CONNECTIONS:\n" + "\n".join(f"  - {e}" for e in gs["high_severity_edges"]))

        # All signals (abbreviated)
        if context["signals"]:
            signal_lines = []
            for i, s in enumerate(context["signals"][:15]):
                companies = ", ".join(s.get("company_names", []))
                sources_count = len(s.get("sources", []))
                signal_lines.append(
                    f"{i+1}. [{s.get('severity', '?').upper()}] {s.get('headline', 'No headline')} "
                    f"| {s.get('confidence', 0)}% confidence "
                    f"| Type: {s.get('signal_type', '')} "
                    f"| Companies: {companies} "
                    f"| Freshness: {s.get('freshness', '')} "
                    f"| {sources_count} source articles"
                )
            parts.append("ACTIVE SIGNALS:\n" + "\n".join(signal_lines))

        # Accuracy data
        acc = context.get("accuracy", {})
        if acc.get("total_tracked", 0) > 0:
            parts.append(
                f"ACCURACY TRACK RECORD: {acc['correct']}/{acc['total_tracked']} predictions correct "
                f"({acc['accuracy_pct']}% accuracy rate, T+3 day verification)"
            )

        # Portfolio context
        if portfolio:
            parts.append(f"USER PORTFOLIO: {', '.join(portfolio)}")
            # Find portfolio-relevant signals
            portfolio_upper = [t.upper() for t in portfolio]
            relevant = [
                s for s in context["signals"]
                if any(t.upper() in portfolio_upper for t in s.get("nse_tickers", []))
                or s.get("portfolio_relevance") == "direct"
            ]
            if relevant:
                rel_str = "; ".join(
                    f"{s.get('headline','')} ({s.get('confidence',0)}%)" for s in relevant[:5]
                )
                parts.append(f"SIGNALS AFFECTING PORTFOLIO: {rel_str}")
            else:
                parts.append("No active signals directly affect the user's portfolio holdings.")

        # Selected signal full detail
        if signal_id and context["signals"]:
            match = next((s for s in context["signals"] if s.get("id") == signal_id), None)
            if match:
                # Include source article titles and details
                source_info = "\n".join(
                    f"  - {src.get('title', 'Untitled')} ({src.get('source', 'Unknown')})"
                    for src in match.get("sources", [])[:5]
                )
                parts.append(
                    f"\nSELECTED SIGNAL DETAIL:\n"
                    f"Headline: {match.get('headline', '')}\n"
                    f"Summary: {match.get('summary', '')}\n"
                    f"Confidence: {match.get('confidence', 0)}% | Severity: {match.get('severity', '')}\n"
                    f"Signal Type: {match.get('signal_type', '')}\n"
                    f"Companies: {', '.join(match.get('company_names', []))}\n"
                    f"Contagion: {match.get('contagion_type', 'isolated')} - {match.get('contagion_note', '')}\n"
                    f"Source Articles:\n{source_info}\n"
                    f"What to Watch: {match.get('what_to_watch', '')}"
                )

        context_str = "\n\n".join(parts) if parts else "No data available yet. Pipeline may still be running."

        user_msg = f"""Current intelligence data:

{context_str}

User question: {query}"""

        try:
            models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
            response = None
            for model in models:
                try:
                    response = await self.client.chat.completions.create(
                        model=model,
                        temperature=0.1,
                        max_tokens=2048,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_msg},
                        ],
                    )
                    break
                except Exception as e:
                    logger.warning(f"Chat model {model} failed: {e}")
                    continue

            if not response:
                return {"text": "All models unavailable. Try again shortly.", "audio_path": ""}

            answer_text = response.choices[0].message.content.strip()

            # Generate English TTS via Groq Orpheus
            audio_path = await self._generate_voice(answer_text, query[:20])

            return {"text": answer_text, "audio_path": audio_path}

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {"text": f"Error processing query: {str(e)[:100]}", "audio_path": ""}

    async def _generate_voice(self, text: str, query_hint: str) -> str:
        """Generate English TTS using Groq Orpheus."""
        try:
            import hashlib
            file_id = hashlib.md5(text[:50].encode()).hexdigest()[:8]
            filepath = os.path.join(AUDIO_DIR, f"chat_{file_id}.wav")

            if os.path.exists(filepath):
                return f"chat_{file_id}.wav"

            voiced = f"[focused] {text}"
            response = await self.client.audio.speech.create(
                model="canopylabs/orpheus-v1-english",
                voice="austin",
                input=voiced,
                response_format="wav",
            )
            response.write_to_file(filepath)
            return f"chat_{file_id}.wav"
        except Exception as e:
            logger.warning(f"Orpheus TTS failed: {e}")
            return ""
