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
    scheduler.add_job(scheduled_run, "interval", minutes=15, id="pipeline_run")
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
            signals.sort(key=lambda s: 0 if s.get("portfolio_relevance") == "direct" else 1)

        # Include accuracy summary
        from services.accuracy_tracker import AccuracyTracker
        accuracy = AccuracyTracker()
        accuracy_summary = accuracy.get_accuracy_summary()

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
    """Stream Hindi audio brief for a signal."""
    audio_path = os.path.join(AUDIO_DIR, f"{signal_id}.mp3")
    if os.path.exists(audio_path):
        return FileResponse(audio_path, media_type="audio/mpeg", filename=f"{signal_id}.mp3")
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


@app.get("/api/backtest/adani")
async def get_adani_backtest():
    """Return Adani Jan 2023 illustrative backtest scenario."""
    return {
        "title": "Adani Group — January 2023 (Illustrative)",
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


@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
