"""
ChromaDB wrapper for ET Mosaic.
Handles article storage and semantic search.
"""

import chromadb
from chromadb.config import Settings
import os
import json
import logging

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class ChromaStore:
    def __init__(self, persist_dir: str = None):
        if persist_dir is None:
            persist_dir = os.path.join(DATA_DIR, "chromadb")
        self.client = chromadb.Client(Settings(
            persist_directory=persist_dir,
            anonymized_telemetry=False,
            is_persistent=True
        ))
        self.collection = self.client.get_or_create_collection(
            name="articles",
            metadata={"hnsw:space": "cosine"}
        )

    def add_articles(self, articles: list[dict], embeddings: list[list[float]]):
        """Add articles with pre-computed embeddings."""
        if not articles:
            return
        ids = [a["id"] for a in articles]
        documents = [f"{a['title']} {a['description']}" for a in articles]
        metadatas = []
        for a in articles:
            meta = {
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "source_channel": a.get("source_channel", ""),
                "published_at": a.get("published_at", ""),
                "sector": a.get("sector", "Other"),
                "is_global_macro": str(a.get("is_global_macro", False)),
                "sentiment": float(a.get("sentiment", 0.0)),
            }
            if a.get("nse_tickers"):
                meta["nse_tickers"] = json.dumps(a["nse_tickers"])
            if a.get("signal_keywords"):
                meta["signal_keywords"] = json.dumps(a["signal_keywords"])
            metadatas.append(meta)

        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"Added {len(ids)} articles to ChromaDB")
        except Exception as e:
            logger.error(f"ChromaDB add error: {e}")

    def query_similar(self, embedding: list[float], n_results: int = 20,
                      where: dict = None) -> dict:
        """Query similar articles by embedding."""
        try:
            kwargs = {
                "query_embeddings": [embedding],
                "n_results": n_results,
            }
            if where:
                kwargs["where"] = where
            return self.collection.query(**kwargs)
        except Exception as e:
            logger.error(f"ChromaDB query error: {e}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def get_recent_articles(self, days: int = 7) -> dict:
        """Get all articles from the collection (filter by date in caller)."""
        try:
            result = self.collection.get(
                include=["embeddings", "documents", "metadatas"]
            )
            return result
        except Exception as e:
            logger.error(f"ChromaDB get error: {e}")
            return {"ids": [], "documents": [], "metadatas": [], "embeddings": []}

    def count(self) -> int:
        return self.collection.count()
