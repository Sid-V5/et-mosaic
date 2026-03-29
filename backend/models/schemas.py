"""
ET Mosaic — Pydantic v2 data models.
All other modules import from here.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


# --- Enums ---

class SignalType(str, Enum):
    TRIPLE_THREAT = "TRIPLE_THREAT"
    GOVERNANCE_DETERIORATION = "GOVERNANCE_DETERIORATION"
    REGULATORY_CONVERGENCE = "REGULATORY_CONVERGENCE"
    SILENT_ACCUMULATION = "SILENT_ACCUMULATION"
    SENTIMENT_VELOCITY = "SENTIMENT_VELOCITY"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActionType(str, Enum):
    ADD_WATCHLIST = "ADD_WATCHLIST"
    REDUCE_EXPOSURE = "REDUCE_EXPOSURE"
    INCREASE_MONITORING = "INCREASE_MONITORING"


class PipelineStatus(str, Enum):
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class ContagionType(str, Enum):
    ISOLATED = "isolated"
    SPREADING = "spreading"
    SYSTEMIC = "systemic"


# --- Core Models ---

class Article(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    description: str
    url: str
    published_at: datetime
    source_channel: str
    is_global_macro: bool = False
    sector: str = "Other"
    nse_tickers: list[str] = Field(default_factory=list)
    signal_keywords: list[str] = Field(default_factory=list)
    sentiment: float = 0.0
    embedding: list[float] = Field(default_factory=list)


class ActionRecommendation(BaseModel):
    type: ActionType
    reasoning: str
    confidence: float


class Connection(BaseModel):
    article_ids: list[str]
    company_names: list[str]
    nse_tickers: list[str]
    signal_type: SignalType
    pattern_matched: str
    confidence: float
    severity: Severity
    explanation: str
    market_data_confirmation: float = 0.0
    historical_match: float = 0.0
    sentiment_velocity: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SignalCard(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    headline: str
    summary: str
    what_to_watch: str
    signal_type: SignalType
    severity: Severity
    freshness: str = "RECENT"
    confidence: float
    sources: list[dict] = Field(default_factory=list)
    contagion_note: str = ""
    historical_match: float = 0.0
    similarity: float = 0.0
    sentiment_velocity: float = 0.0
    market_data_confirmation: float = 0.0
    portfolio_relevance: str = "none"
    action_recommendation: ActionRecommendation
    audio_path: str = ""
    disclaimer: str = "This is for research only. Not investment advice."
    company_names: list[str] = Field(default_factory=list)
    nse_tickers: list[str] = Field(default_factory=list)
    bulk_deals: list = Field(default_factory=list)
    price_data: dict = Field(default_factory=dict)
    technical: dict = Field(default_factory=dict)
    contagion_type: str = "isolated"
    affected_peers: list[str] = Field(default_factory=list)
    sector: str = "Other"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    composite_score: float = 0.0
    # Competition-critical fields
    analysis_chain: list[dict] = Field(default_factory=list)
    conflicting_signals: dict = Field(default_factory=dict)
    filing_citation: list[str] = Field(default_factory=list)
    portfolio_impact: dict = Field(default_factory=dict)
    matched_holdings: list[str] = Field(default_factory=list)


class AuditEntry(BaseModel):
    step: str
    agent_or_service: str
    status: str
    duration_ms: float
    output_summary: str


class PipelineState(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: PipelineStatus = PipelineStatus.RUNNING
    articles_ingested: int = 0
    extractions_complete: int = 0
    signals_found: int = 0
    errors: list[str] = Field(default_factory=list)
    audit_trail: list[AuditEntry] = Field(default_factory=list)


# --- Graph Models (for D3 frontend) ---

class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # "article" | "company" | "signal"
    sector: str = "Other"
    confidence: float = 0.0
    connections_count: int = 0
    metadata: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    severity: Severity = Severity.LOW
    confidence: float = 0.0
    label: str = ""
