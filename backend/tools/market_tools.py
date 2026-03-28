"""
Market Tools — yfinance batch download wrapper.
"""

import asyncio
import logging
import yfinance as yf

logger = logging.getLogger(__name__)


async def batch_download(tickers: list[str], period: str = "90d") -> dict:
    """Download OHLCV data for multiple NSE tickers."""
    try:
        def _download():
            ns_tickers = [f"{t}.NS" for t in tickers]
            ticker_str = " ".join(ns_tickers)
            df = yf.download(ticker_str, period=period, auto_adjust=True, progress=False, group_by="ticker")
            return df
        return await asyncio.to_thread(_download)
    except Exception as e:
        logger.error(f"batch_download error: {e}")
        return None


async def get_ticker_info(ticker: str) -> dict:
    """Get basic info about an NSE ticker."""
    try:
        def _info():
            t = yf.Ticker(f"{ticker}.NS")
            info = t.info
            return {
                "name": info.get("longName", ticker),
                "sector": info.get("sector", "Other"),
                "industry": info.get("industry", ""),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", 0),
                "dividend_yield": info.get("dividendYield", 0),
            }
        return await asyncio.to_thread(_info)
    except Exception as e:
        logger.error(f"get_ticker_info error for {ticker}: {e}")
        return {"name": ticker, "sector": "Other"}
