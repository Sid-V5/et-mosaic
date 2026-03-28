"""
PgVector wrapper for ET Mosaic.
Replaces ChromaDB for enterprise scalability and hybrid search.
"""

import os
import json
import logging
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
        self.Session = sessionmaker(bind=self.engine)

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
                    
                doc = f"{article.get('title', '')} {article.get('description', '')}"
                
                # Upsert query using Postgres ON CONFLICT DO UPDATE
                stmt = insert(ArticleModel).values(
                    id=article["id"],
                    document=doc,
                    metadata_json=meta,
                    embedding=embed
                )
                
                # If we encounter a duplicate hash ID, overwrite it
                update_dict = {
                    c.name: c for c in stmt.excluded if not c.primary_key
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=['id'],
                    set_=update_dict
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
        """Query similar articles by embedding."""
        try:
            with self.Session() as session:
                query = session.query(ArticleModel)
                
                # Handle basic chroma 'where' equality filters using JSONB
                if where:
                    for k, v in where.items():
                        # Using text queries for postgres jsonb extraction checks
                        query = query.filter(text(f"metadata_json->>'{k}' = '{v}'"))
                
                # Order by vector L2 distance
                results = query.order_by(ArticleModel.embedding.l2_distance(embedding)).limit(n_results).all()
                
                return {
                    "ids": [[r.id for r in results]],
                    "documents": [[r.document for r in results]],
                    "metadatas": [[r.metadata_json for r in results]],
                    "distances": [[0.0 for _ in results]] # Postgres gives absolute distance, we could map this
                }
        except Exception as e:
            logger.error(f"pgvector query error: {e}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def get_recent_articles(self, days: int = 7) -> dict:
        """Get all articles from the collection (filter by date in caller, keeping Chroma parity)."""
        try:
            with self.Session() as session:
                results = session.query(ArticleModel).all()
                return {
                    "ids": [r.id for r in results],
                    "documents": [r.document for r in results],
                    "metadatas": [r.metadata_json for r in results],
                    "embeddings": [r.embedding for r in results] # Return raw arrays
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
