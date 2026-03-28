"""
Data Ingestion Service — RSS feed ingestion, dedup, embed, store in ChromaDB.
Deterministic — no LLM.
"""

import asyncio
import hashlib
import json
import os
import logging
from datetime import datetime, timedelta, timezone

import aiohttp
import aiofiles
import feedparser
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SEEN_URLS_PATH = os.path.join(DATA_DIR, "seen_urls.json")

RSS_FEEDS = [
    {"url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "channel": "ET Markets", "is_global_macro": False},
    {"url": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms", "channel": "ET Stocks", "is_global_macro": False},
    {"url": "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms", "channel": "ET Economy", "is_global_macro": False},
    {"url": "https://economictimes.indiatimes.com/news/company/corporate-trends/rssfeeds/13357212.cms", "channel": "ET Corporate", "is_global_macro": False},
    {"url": "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms", "channel": "ET Tech", "is_global_macro": False},
    {"url": "https://economictimes.indiatimes.com/news/politics-and-nation/rssfeeds/1052732854.cms", "channel": "ET Policy", "is_global_macro": False},
    {"url": "https://feeds.reuters.com/reuters/businessNews", "channel": "Reuters", "is_global_macro": True},
    {"url": "https://finance.yahoo.com/news/rssindex", "channel": "Yahoo Finance", "is_global_macro": True},
]


class DataIngestionService:
    def __init__(self, chroma_store=None):
        self.chroma_store = chroma_store
        self.embedder = None

    def _load_embedder(self):
        if self.embedder is None:
            from sentence_transformers import SentenceTransformer
            # BGE-M3 provides highly accurate 1024-dimensional embeddings
            self.embedder = SentenceTransformer("BAAI/bge-m3")

    def _load_seen_urls(self) -> set:
        try:
            with open(SEEN_URLS_PATH, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return set(data.keys())
                return set(data)
        except Exception:
            return set()

    async def _save_seen_urls(self, seen: set):
        data = {url: True for url in seen}
        async with aiofiles.open(SEEN_URLS_PATH, "w") as f:
            await f.write(json.dumps(data, indent=2))

    async def _fetch_one_feed(self, session: aiohttp.ClientSession, feed_config: dict) -> list[dict]:
        """Fetch and parse a single RSS feed."""
        url = feed_config["url"]
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.warning(f"Feed {url} returned status {resp.status}")
                    return []
                content = await resp.text()

            parsed = feedparser.parse(content)
            articles = []
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)

            for entry in parsed.entries:
                try:
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        from time import mktime
                        published = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        from time import mktime
                        published = datetime.fromtimestamp(mktime(entry.updated_parsed), tz=timezone.utc)
                    else:
                        published = datetime.now(timezone.utc)

                    if published < cutoff:
                        continue

                    description = entry.get("summary", entry.get("description", ""))
                    if description:
                        soup = BeautifulSoup(description, "html.parser")
                        description = soup.get_text(strip=True)[:500]

                    articles.append({
                        "title": entry.get("title", ""),
                        "description": description,
                        "url": entry.get("link", ""),
                        "published_at": published.isoformat(),
                        "source_channel": feed_config["channel"],
                        "is_global_macro": feed_config["is_global_macro"],
                    })
                except Exception as e:
                    logger.error(f"Error parsing entry from {url}: {e}")
                    continue

            return articles
        except Exception as e:
            logger.error(f"Error fetching feed {url}: {e}")
            return []

    async def run(self) -> dict:
        """Main ingestion pipeline."""
        result = {
            "new_count": 0,
            "skipped": 0,
            "errors": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        seen_urls = self._load_seen_urls()

        # Fetch all feeds in parallel
        async with aiohttp.ClientSession(
            headers={"User-Agent": "ETMosaic/1.0 (research project)"}
        ) as session:
            tasks = [self._fetch_one_feed(session, feed) for feed in RSS_FEEDS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Feed fetch exception: {r}")
                result["errors"] += 1
                continue
            all_articles.extend(r)

        # Dedup
        new_articles = []
        for article in all_articles:
            url_hash = hashlib.md5(article["url"].encode()).hexdigest()
            if url_hash in seen_urls:
                result["skipped"] += 1
                continue
            seen_urls.add(url_hash)
            article["id"] = url_hash[:12]
            new_articles.append(article)

        if not new_articles:
            result["new_count"] = 0
            await self._save_seen_urls(seen_urls)
            return result

        # Embed
        self._load_embedder()
        texts = [f"{a['title']} {a['description']}" for a in new_articles]
        embeddings = await asyncio.to_thread(
            self.embedder.encode, texts, batch_size=32
        )
        embeddings_list = [emb.tolist() for emb in embeddings]

        # Store in ChromaDB
        if self.chroma_store:
            self.chroma_store.add_articles(new_articles, embeddings_list)

        # Save seen URLs
        await self._save_seen_urls(seen_urls)

        result["new_count"] = len(new_articles)
        logger.info(f"Ingested {len(new_articles)} new articles, skipped {result['skipped']}")
        return result
