"""
Enrichment Tools — Wikipedia lookup and sentiment velocity.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def wikipedia_summary(company: str) -> str:
    """Get Wikipedia summary for a company."""
    try:
        def _fetch():
            try:
                import wikipediaapi
                wiki = wikipediaapi.Wikipedia(
                    user_agent="ETMosaic/1.0 (research project)",
                    language="en"
                )
                page = wiki.page(company)
                if page.exists():
                    return page.summary[:500]
            except ImportError:
                pass
            return ""
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"wikipedia_summary error for {company}: {e}")
        return ""


def compute_sentiment_velocity(sentiments: list[float], timestamps: list) -> float:
    """
    Compute sentiment velocity — rate of sentiment change over time.
    Negative velocity = sentiment deteriorating.
    """
    if len(sentiments) < 2:
        return 0.0
    try:
        diffs = [sentiments[i] - sentiments[i-1] for i in range(1, len(sentiments))]
        velocity = sum(diffs) / len(diffs)
        return round(velocity, 4)
    except Exception:
        return 0.0
