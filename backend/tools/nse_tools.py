"""
NSE Tools — 4 async functions for NSE India market data.
fetch_bulk_deals, fetch_insider_trades, fetch_price_volume, get_sector_peers
"""

import asyncio
import logging
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

SECTOR_PEERS = {
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "BANKBARODA", "PNB"],
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "MPHASIS", "COFORGE"],
    "Metals": ["TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL", "NATIONALUM", "SAIL", "NMDC", "COALINDIA"],
    "Energy": ["RELIANCE", "ONGC", "BPCL", "HPCL", "IOC", "GAIL", "POWERGRID", "NTPC"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP", "LUPIN", "AUROPHARMA", "BIOCON"],
    "Auto": ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "ASHOKLEY", "TVSMOTOR"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "GODREJCP", "COLPAL"],
    "Infra": ["LT", "ADANIENT", "ADANIPORTS", "ULTRACEMCO", "GRASIM", "ACC", "AMBUJACEM", "DLF"],
    "NBFC": ["BAJFINANCE", "BAJAJFINSV", "SBILIFE", "HDFCLIFE", "ICICIPRULI", "MUTHOOTFIN", "CHOLAFIN", "SHRIRAMFIN"],
    "Telecom": ["BHARTIARTL", "IDEA", "TATACOMM", "ROUTE", "STERLITE", "HFCL", "TEJAS", "RAILTEL"],
}


async def fetch_bulk_deals(company: str, days: int = 7) -> list[dict]:
    """Fetch bulk/block deals from NSE for a company."""
    try:
        def _fetch():
            session = requests.Session()
            session.headers.update(NSE_HEADERS)
            session.get("https://www.nseindia.com", timeout=10)
            resp = session.get(
                "https://www.nseindia.com/api/snapshot-capital-market-largedeal",
                timeout=10
            )
            if resp.status_code != 200:
                return []
            data = resp.json().get("data", [])
            results = []
            company_lower = company.lower()
            for deal in data:
                stock_name = deal.get("symbol", "").lower()
                client_name = deal.get("clientName", "").lower()
                if company_lower in stock_name or company_lower in client_name:
                    results.append({
                        "client": deal.get("clientName", ""),
                        "stock": deal.get("symbol", ""),
                        "qty": deal.get("qty", 0),
                        "price": deal.get("wAvgPrice", 0),
                        "side": deal.get("buySell", ""),
                    })
            return results
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"fetch_bulk_deals error for {company}: {e}")
        return []


async def fetch_insider_trades(company: str) -> list[dict]:
    """Fetch insider trading data for a company."""
    try:
        def _fetch():
            session = requests.Session()
            session.headers.update(NSE_HEADERS)
            session.get("https://www.nseindia.com", timeout=10)
            resp = session.get(
                f"https://www.nseindia.com/api/corporates-pit?index=equities&from_date=&to_date=&symbol={company.upper()}",
                timeout=10
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            if isinstance(data, list):
                return data[:20]
            return data.get("data", [])[:20]
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"fetch_insider_trades error for {company}: {e}")
        return []


async def fetch_price_volume(tickers: list[str], days: int = 14) -> dict:
    """Fetch price and volume data for multiple tickers via yfinance."""
    try:
        def _fetch():
            results = {}
            ticker_str = " ".join([f"{t}.NS" for t in tickers])
            df = yf.download(ticker_str, period="60d", group_by="ticker", auto_adjust=True, progress=False)

            for ticker in tickers:
                try:
                    ns_ticker = f"{ticker}.NS"
                    if len(tickers) == 1:
                        tdata = df
                    else:
                        if ns_ticker not in df.columns.get_level_values(0):
                            results[ticker] = {"error": "no_data"}
                            continue
                        tdata = df[ns_ticker]

                    if tdata.empty or len(tdata) < 5:
                        results[ticker] = {"error": "insufficient_data"}
                        continue

                    # Flatten multi-level columns if needed
                    if hasattr(tdata.columns, 'levels'):
                        tdata.columns = tdata.columns.get_level_values(-1)

                    close = tdata["Close"].dropna()
                    volume = tdata["Volume"].dropna()

                    if len(close) < 5:
                        results[ticker] = {"error": "insufficient_data"}
                        continue

                    current_price = float(close.iloc[-1])
                    volume_today = float(volume.iloc[-1])
                    volume_20d_avg = float(volume.tail(20).mean())
                    volume_spike = volume_today > 2 * volume_20d_avg

                    price_7d_ago = float(close.iloc[-min(7, len(close))])
                    price_change_7d_pct = ((current_price - price_7d_ago) / price_7d_ago) * 100

                    sma_200 = float(close.tail(200).mean()) if len(close) >= 200 else float(close.mean())
                    above_200dma = current_price > sma_200

                    low_52w = float(close.tail(min(252, len(close))).min())
                    near_52w_low = current_price <= low_52w * 1.05

                    results[ticker] = {
                        "current_price": round(current_price, 2),
                        "volume_today": int(volume_today),
                        "volume_20d_avg": int(volume_20d_avg),
                        "volume_spike": volume_spike,
                        "price_change_7d_pct": round(price_change_7d_pct, 2),
                        "above_200dma": above_200dma,
                        "near_52w_low": near_52w_low,
                    }
                except Exception as inner_e:
                    logger.error(f"Error processing {ticker}: {inner_e}")
                    results[ticker] = {"error": str(inner_e)}
            return results

        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"fetch_price_volume error: {e}")
        return {}


def get_sector_peers(company: str, sector: str) -> list[str]:
    """Return hardcoded top 8 NSE peers for a sector."""
    peers = SECTOR_PEERS.get(sector, SECTOR_PEERS.get("Other", []))
    return [p for p in peers if p.upper() != company.upper()][:8]
