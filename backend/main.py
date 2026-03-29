# pyre-ignore-all-errors
"""
ET Mosaic — FastAPI backend with APScheduler.
Runs the MosaicOrchestrator every 15 minutes.
"""

import json
import os
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from dotenv import load_dotenv  # type: ignore[import-untyped]

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")

# Global orchestrator instance
orchestrator = None
scheduler = AsyncIOScheduler()


async def scheduled_run():
    """Scheduled pipeline run."""
    global orchestrator
    if orchestrator:
        logger.info("Scheduled pipeline run starting...")
        try:
            await orchestrator.run()
        except Exception as e:
            logger.error(f"Scheduled run error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global orchestrator
    from orchestrator import MosaicOrchestrator
    orchestrator = MosaicOrchestrator()
    logger.info("MosaicOrchestrator initialized")

    # Schedule every 15 minutes
    scheduler.add_job(scheduled_run, "interval", minutes=15, id="pipeline_run",
                       max_instances=1, misfire_grace_time=300)
    scheduler.start()
    logger.info("Scheduler started (every 15 min)")

    # Run once on startup — NON-BLOCKING so the API server starts immediately
    import asyncio
    asyncio.create_task(scheduled_run())
    logger.info("Initial pipeline run started in background")

    yield

    scheduler.shutdown()
    logger.info("Shutdown complete")


app = FastAPI(title="ET Mosaic API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/signals")
async def get_signals(
    portfolio: str = Query(default="", description="Comma-separated NSE tickers"),
    q: str = Query(default="", description="Search query"),
):
    """Get signal cards, optionally filtered by portfolio and search query."""
    try:
        # Save user portfolio for scheduled pipeline runs (Scenario 3)
        if portfolio:
            tickers_list = [t.strip().upper() for t in portfolio.split(",") if t.strip()]
            if tickers_list:
                try:
                    portfolio_path = os.path.join(DATA_DIR, "user_portfolio.json")
                    with open(portfolio_path, "w") as f:
                        json.dump(tickers_list, f)
                except Exception:
                    pass
        signals_path = os.path.join(DATA_DIR, "signals.json")
        with open(signals_path, "r") as f:
            signals = json.load(f)

        if not signals:
            signals = []

        # Filter by search query
        if q:
            q_lower = q.lower()
            signals = [s for s in signals if (
                q_lower in s.get("headline", "").lower() or
                q_lower in s.get("summary", "").lower() or
                any(q_lower in c.lower() for c in s.get("company_names", [])) or
                any(q_lower in t.lower() for t in s.get("nse_tickers", []))
            )]

        # Sort by portfolio relevance
        if portfolio:
            tickers = [t.strip().upper() for t in portfolio.split(",") if t.strip()]
            for s in signals:
                signal_tickers = [t.upper() for t in s.get("nse_tickers", [])]
                if any(t in tickers for t in signal_tickers):
                    s["portfolio_relevance"] = "direct"

        # Sort: BREAKING first, then portfolio-direct, then by confidence
        def signal_sort_key(s):
            breaking = 0 if s.get("freshness") == "BREAKING" else 1
            portfolio_rank = 0 if s.get("portfolio_relevance") == "direct" else 1
            confidence = -(s.get("confidence", 0))  # negative for desc
            return (breaking, portfolio_rank, confidence)
        signals.sort(key=signal_sort_key)

        # Rebuild analysis chains on-the-fly (ensures latest 7-step format)
        try:
            from agents.narrator import NarratorAgent
            narrator = NarratorAgent.__new__(NarratorAgent)
            for s in signals:
                s["analysis_chain"] = narrator._build_analysis_chain(s)
        except Exception as e:
            logger.warning(f"Could not rebuild analysis chains: {e}")

        # Use orchestrator's cached accuracy instance instead of creating a new one per request
        global orchestrator
        accuracy_summary = {}
        if orchestrator and hasattr(orchestrator, 'accuracy'):
            accuracy_summary = orchestrator.accuracy.get_accuracy_summary()
        else:
            try:
                from services.accuracy_tracker import AccuracyTracker
                accuracy_summary = AccuracyTracker().get_accuracy_summary()
            except Exception:
                pass

        return {
            "signals": signals,
            "count": len(signals),
            "accuracy_summary": accuracy_summary,
        }

    except Exception as e:
        logger.error(f"Error getting signals: {e}")
        return {"signals": [], "count": 0, "accuracy_summary": {}}


@app.get("/api/graph")
async def get_graph():
    """Get knowledge graph data for D3 visualization."""
    try:
        graph_path = os.path.join(DATA_DIR, "graph_data.json")
        with open(graph_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error getting graph: {e}")
        return {"nodes": [], "edges": []}


@app.get("/api/signal/{signal_id}/audio")
async def get_signal_audio(signal_id: str):
    """Stream audio brief for a signal. Checks both .wav (Orpheus) and .mp3 (gTTS)."""
    # Check for Orpheus-generated .wav first (higher quality)
    wav_path = os.path.join(AUDIO_DIR, f"{signal_id}.wav")
    if os.path.exists(wav_path):
        return FileResponse(wav_path, media_type="audio/wav", filename=f"{signal_id}.wav")
    # Fallback to gTTS-generated .mp3
    mp3_path = os.path.join(AUDIO_DIR, f"{signal_id}.mp3")
    if os.path.exists(mp3_path):
        return FileResponse(mp3_path, media_type="audio/mpeg", filename=f"{signal_id}.mp3")
    return JSONResponse(status_code=404, content={"error": "Audio not found"})


@app.get("/api/pipeline/status")
async def get_pipeline_status():
    """Get current pipeline status."""
    global orchestrator
    if orchestrator:
        return orchestrator.current_state
    return {
        "run_id": "",
        "started_at": "",
        "status": "idle",
        "articles_ingested": 0,
        "extractions_complete": 0,
        "signals_found": 0,
        "errors": [],
        "audit_trail": [],
    }

@app.post("/api/pipeline/trigger")
async def trigger_pipeline():
    """Manually trigger a pipeline run."""
    import asyncio
    global orchestrator
    if not orchestrator:
        return JSONResponse(status_code=500, content={"error": "Orchestrator not initialized"})
    
    if orchestrator.current_state.get("status") == "running":
        return {"status": "already_running"}
        
    asyncio.create_task(scheduled_run())
    return {"status": "started"}


@app.get("/api/portfolio-impact")
async def get_portfolio_impact(portfolio: str = ""):
    """
    Scenario 3: Calculate quantified ₹ P&L impact of all signals on user's portfolio.
    Returns signals ranked by materiality with per-holding impact estimates.
    """
    if not portfolio:
        return {"error": "Portfolio required. Pass comma-separated tickers.", "signals": []}
    
    tickers = [t.strip().upper() for t in portfolio.split(",") if t.strip()]
    
    try:
        # Load signals
        signals_path = os.path.join(DATA_DIR, "signals.json")
        with open(signals_path, "r") as f:
            signals = json.load(f)
        
        global orchestrator
        scoring = orchestrator.scoring if orchestrator else None
        if not scoring:
            from services.scoring_engine import ScoringEngine
            scoring = ScoringEngine()
        
        # Calculate impact for each signal
        impacted = []
        for signal in signals:
            impact = scoring.estimate_portfolio_impact(signal, tickers)
            if impact.get("materiality", "NONE") != "NONE":
                signal["portfolio_impact"] = impact
                impacted.append(signal)
        
        # Sort by materiality (HIGH > MEDIUM > LOW)
        mat_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        impacted.sort(key=lambda s: mat_order.get(
            s.get("portfolio_impact", {}).get("materiality", "LOW"), 2
        ))
        
        return {
            "portfolio": tickers,
            "signals": impacted,
            "count": len(impacted),
            "total_portfolio_value": len(tickers) * 100000,  # Default ₹1L per stock
        }
    except Exception as e:
        logger.error(f"Portfolio impact error: {e}")
        return {"error": str(e), "signals": []}


@app.get("/api/fii-dii")
async def get_fii_dii():
    """Fetch latest FII/DII trading activity data."""
    try:
        from tools.nse_tools import fetch_fii_dii_activity
        return await fetch_fii_dii_activity()
    except Exception as e:
        logger.error(f"FII/DII endpoint error: {e}")
        return {"raw_data": [], "summary": {"error": str(e)}}


@app.get("/api/backtest/adani")
async def get_adani_backtest():
    """Return Adani Jan 2023 illustrative backtest scenario."""
    return {
        "title": "Adani Group - January 2023 (Illustrative)",
        "description": "How ET Mosaic would have connected public signals before the Hindenburg report.",
        "events": [
            {
                "date": "2023-01-18",
                "type": "ET Article",
                "title": "FIIs pull \u20b98000Cr from Adani stocks",
                "source": "ET Markets",
                "color": "blue",
            },
            {
                "date": "2023-01-20",
                "type": "ET Article",
                "title": "Adani Group debt levels under analyst scrutiny",
                "source": "ET Economy",
                "color": "blue",
            },
            {
                "date": "2023-01-21",
                "type": "NSE Bulk Deal",
                "title": "Large sell block in Adani Enterprises",
                "source": "NSE",
                "color": "amber",
            },
            {
                "date": "2023-01-21",
                "type": "ET Mosaic Signal",
                "title": "CONVERGENCE SIGNAL fired \u2014 78% confidence",
                "source": "System",
                "color": "green",
            },
            {
                "date": "2023-01-25",
                "type": "Market Event",
                "title": "Hindenburg report published",
                "source": "External",
                "color": "red",
            },
        ],
        "mosaic_confidence": 78,
        "signal_type": "TRIPLE_THREAT",
        "historical_accuracy": 73,
        "note": "Illustrative backtest based on publicly available information from January 2023.",
        "disclaimer": "This is for research only. Not investment advice. All data points referenced are from public sources.",
    }


@app.post("/api/action")
async def post_action(data: dict):
    """Log an action taken on a signal."""
    logger.info(f"Action taken: signal_id={data.get('signal_id')}, action={data.get('action_type')}")
    return {"status": "logged", "signal_id": data.get("signal_id"), "action": data.get("action_type")}


# ── Agentic terminal chat ─────────────────────────────────────
mosaic_chat = None

@app.post("/api/chat")
async def chat_query(data: dict):
    """Answer intelligence queries using graph + signals context."""
    global mosaic_chat
    if mosaic_chat is None:
        from agents.mosaic_chat import MosaicChat
        mosaic_chat = MosaicChat()

    query = data.get("query", "").strip()
    if not query:
        return {"text": "Empty query.", "audio_path": ""}

    signal_id = data.get("signal_id", None)
    portfolio = data.get("portfolio", [])
    result = await mosaic_chat.answer(query, signal_id, portfolio)
    return result


@app.get("/api/chat/audio/{filename}")
async def chat_audio(filename: str):
    """Stream Orpheus voice response."""
    audio_path = os.path.join(AUDIO_DIR, filename)
    if os.path.exists(audio_path):
        return FileResponse(audio_path, media_type="audio/wav", filename=filename)
    return JSONResponse(status_code=404, content={"error": "Audio not found"})


@app.get("/api/architecture")
async def get_architecture():
    """Return the full multi-agent architecture for judges/documentation."""
    return {
        "name": "ET Mosaic",
        "tagline": "Autonomous market intelligence for the Indian retail investor",
        "pipeline_steps": 7,
        "agents": [
            {
                "name": "DataIngestion",
                "model": "None (RSS + HTTP)",
                "role": "Scrape 8 ET/Reuters/Yahoo feeds, dedup via URL hash, embed articles using BGE-M3 (1024D)",
                "step": 1,
                "autonomous": True,
            },
            {
                "name": "ExtractorAgent",
                "model": "LLaMA 3.3 70B (Groq)",
                "role": "Extract company names, NSE tickers, sectors, sentiment, event types from raw articles",
                "step": 2,
                "autonomous": True,
            },
            {
                "name": "MosaicBuilder",
                "model": "LLaMA 3.3 70B (Groq) + pgvector cosine search",
                "role": "Cross-reference extractions to detect convergence patterns (Triple Threat, Governance Deterioration, etc.)",
                "step": 3,
                "autonomous": True,
            },
            {
                "name": "ContagionAgent",
                "model": "LLaMA 3.1 8B (Groq)",
                "role": "Sector ripple analysis - classify signals as isolated/spreading/systemic by checking peer stocks",
                "step": 4,
                "autonomous": True,
            },
            {
                "name": "NSETools + TechnicalAnalysis",
                "model": "None (nselib + yfinance + pandas-ta)",
                "role": "Fetch bulk/block deals, FII/DII flows, compute RSI/MACD/BBands/52w breakout/golden cross",
                "step": "4b",
                "autonomous": True,
            },
            {
                "name": "ScoringEngine",
                "model": "None (deterministic composite scoring)",
                "role": "Rank signals by freshness + confidence + accuracy + portfolio relevance + contagion. Estimate P&L impact per holding.",
                "step": 5,
                "autonomous": True,
            },
            {
                "name": "NarratorAgent",
                "model": "LLaMA 3.3 70B (Groq) + Orpheus TTS",
                "role": "Generate human-readable signal cards with headline, summary, action recommendation, and audio brief",
                "step": 6,
                "autonomous": True,
            },
            {
                "name": "AccuracyTracker",
                "model": "None (T+3/T+7 price verification via yfinance)",
                "role": "Track signal prediction outcomes against actual price movements. Self-improving accuracy.",
                "step": 7,
                "autonomous": True,
            },
        ],
        "data_sources": [
            "ET Markets RSS", "ET Stocks RSS", "ET Economy RSS",
            "ET Corporate RSS", "ET Tech RSS", "ET Policy RSS",
            "Reuters Business RSS", "Yahoo Finance RSS",
            "NSE Bulk/Block Deals (nselib)", "NSE FII/DII Activity",
            "yfinance Price + Volume Data",
        ],
        "models": {
            "embedding": "BAAI/bge-m3 (1024D, runs locally, $0)",
            "reasoning": "LLaMA 3.3 70B via Groq free tier ($0)",
            "fast_classification": "LLaMA 3.1 8B via Groq free tier ($0)",
            "fallback": "Gemini Pro via Google AI free tier ($0)",
            "tts": "Orpheus TTS via Groq free tier ($0)",
            "database": "PostgreSQL + pgvector (local Docker, $0)",
        },
        "total_cost_per_month": "$0 - entire stack runs on free-tier APIs and local models",
        "error_handling": {
            "groq_rate_limit": "Auto-rotate between 2 API keys, then 30s backoff, then Gemini fallback",
            "feed_failure": "Continue processing cached articles from pgvector",
            "agent_failure": "Graceful degradation - pipeline continues with partial data, errors logged to audit trail",
            "db_failure": "Health endpoint reports degraded status, signals served from JSON cache",
        },
        "hackathon_scenarios": {
            "scenario_1_bulk_deal": "nse_tools.analyze_bulk_deal() detects promoter selling, computes distress score, generates filing citation",
            "scenario_2_breakout": "TechnicalAnalysisService detects 52w breakout + RSI overbought + FII exit = conflicting signals with balanced recommendation",
            "scenario_3_portfolio": "ScoringEngine.estimate_portfolio_impact() quantifies per-holding P&L using sector beta and signal severity",
        },
    }


@app.get("/api/health")
async def health():
    """Health check including DB connectivity."""
    db_ok = False
    try:
        global orchestrator
        if orchestrator and hasattr(orchestrator, 'db'):
            count = orchestrator.db.count()
            db_ok = True
    except Exception:
        pass
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
