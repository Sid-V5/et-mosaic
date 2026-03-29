"""
PgVector wrapper for ET Mosaic.
Enterprise-grade: cosine distance, HNSW indexing, date-filtered retrieval.
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, Column, String, Float, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert
from pgvector.sqlalchemy import Vector

logger = logging.getLogger(__name__)

Base = declarative_base()

class ArticleModel(Base):
    __tablename__ = 'articles'
    
    id = Column(String(255), primary_key=True)
    document = Column(String)
    metadata_json = Column(JSONB)
    embedding = Column(Vector(1024)) # BAAI/bge-m3 outputs 1024 dimensional vectors

class PgVectorStore:
    def __init__(self, connection_string: str = None):
        if connection_string is None:
            # Default to Docker-compose setup
            connection_string = "postgresql://etmosaic:etpassword@localhost:5432/etmosaic"
            
        self.engine = create_engine(connection_string)
        
        # Ensure the vector extension exists before creating tables
        with self.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            
        Base.metadata.create_all(self.engine)
        
        # Create HNSW index for cosine distance — dramatically speeds up similarity search
        self._ensure_hnsw_index()
        self.Session = sessionmaker(bind=self.engine)

    def _ensure_hnsw_index(self):
        """Create HNSW index with cosine distance ops if it doesn't exist."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_article_embedding_cosine "
                    "ON articles USING hnsw (embedding vector_cosine_ops) "
                    "WITH (m = 16, ef_construction = 64)"
                ))
                conn.commit()
                logger.info("HNSW cosine index ensured on articles.embedding")
        except Exception as e:
            logger.warning(f"HNSW index creation skipped (may already exist or not enough data): {e}")

    def add_articles(self, articles: list[dict], embeddings: list[list[float]]):
        """Add articles with pre-computed embeddings."""
        if not articles:
            return
            
        with self.Session() as session:
            for article, embed in zip(articles, embeddings):
                meta = {
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "source_channel": article.get("source_channel", ""),
                    "published_at": article.get("published_at", ""),
                    "sector": article.get("sector", "Other"),
                    "is_global_macro": str(article.get("is_global_macro", False)),
                    "sentiment": float(article.get("sentiment", 0.0)),
                }
                if article.get("nse_tickers"):
                    meta["nse_tickers"] = json.dumps(article["nse_tickers"])
                if article.get("signal_keywords"):
                    meta["signal_keywords"] = json.dumps(article["signal_keywords"])
                if article.get("company_names"):
                    meta["company_names"] = json.dumps(article["company_names"])
                    
                doc = f"{article.get('title', '')} {article.get('description', '')}"
                
                # Upsert query using Postgres ON CONFLICT DO UPDATE
                stmt = insert(ArticleModel).values(
                    id=article["id"],
                    document=doc,
                    metadata_json=meta,
                    embedding=embed
                )
                
                # Explicitly list non-PK columns to update (fixes broken c.primary_key check)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['id'],
                    set_={
                        "document": stmt.excluded.document,
                        "metadata_json": stmt.excluded.metadata_json,
                        "embedding": stmt.excluded.embedding,
                    }
                )
                session.execute(stmt)
            
            try:
                session.commit()
                logger.info(f"Added/Updated {len(articles)} articles in pgvector")
            except Exception as e:
                session.rollback()
                logger.error(f"pgvector add error: {e}")

    def query_similar(self, embedding: list[float], n_results: int = 20,
                      where: dict = None) -> dict:
        """Query similar articles by cosine distance (BGE-M3 standard)."""
        try:
            with self.Session() as session:
                query = session.query(
                    ArticleModel,
                    ArticleModel.embedding.cosine_distance(embedding).label('distance')
                )
                
                # Handle basic chroma 'where' equality filters using JSONB
                # Parameterized queries to prevent SQL injection
                if where:
                    for k, v in where.items():
                        query = query.filter(
                            text("metadata_json->>:key = :val").bindparams(key=k, val=str(v))
                        )
                
                # Order by cosine distance (lower = more similar)
                results = query.order_by('distance').limit(n_results).all()
                
                return {
                    "ids": [[r[0].id for r in results]],
                    "documents": [[r[0].document for r in results]],
                    "metadatas": [[r[0].metadata_json for r in results]],
                    "distances": [[float(r[1]) for r in results]]
                }
        except Exception as e:
            logger.error(f"pgvector query error: {e}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def get_recent_articles(self, days: int = 7) -> dict:
        """Get articles from the last N days only — prevents unbounded memory growth."""
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            with self.Session() as session:
                # Filter by published_at in metadata JSONB (parameterized to prevent injection)
                results = session.query(ArticleModel).filter(
                    text("metadata_json->>'published_at' >= :cutoff").bindparams(cutoff=cutoff)
                ).all()
                
                if not results:
                    # Fallback: if no date-filtered results, return most recent 200
                    results = session.query(ArticleModel).order_by(
                        text("metadata_json->>'published_at' DESC")
                    ).limit(200).all()
                
                return {
                    "ids": [r.id for r in results],
                    "documents": [r.document for r in results],
                    "metadatas": [r.metadata_json for r in results],
                    "embeddings": [r.embedding for r in results]
                }
        except Exception as e:
            logger.error(f"pgvector get error: {e}")
            return {"ids": [], "documents": [], "metadatas": [], "embeddings": []}

    def count(self) -> int:
        try:
            with self.Session() as session:
                return session.query(ArticleModel).count()
        except:
            return 0
