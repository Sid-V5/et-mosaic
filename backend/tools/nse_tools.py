"""
NSE Tools — production-grade market data for ET Mosaic.
Uses nselib for bulk/block deals, FII/DII activity, insider trades + yfinance for price data.
Enhanced for Hackathon Scenarios: bulk deal distress detection, institutional flow analysis.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import yfinance as yf

logger = logging.getLogger(__name__)

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

# Sector beta approximations for Nifty-relative P&L impact estimation
SECTOR_BETA = {
    "Banking": 1.15, "IT": 0.85, "Metals": 1.40, "Energy": 1.10,
    "Pharma": 0.75, "Auto": 1.20, "FMCG": 0.65, "Infra": 1.30,
    "NBFC": 1.25, "Telecom": 0.90, "Other": 1.0,
}

# Known promoter group keywords for bulk deal distress detection
PROMOTER_KEYWORDS = [
    "promoter", "director", "chairman", "founder", "family", "trust",
    "holding", "management", "estate", "spouse", "relative",
]


def _get_ist_dates(days: int = 7):
    """Return (from_date, to_date) strings in DD-MM-YYYY IST format."""
    import zoneinfo
    try:
        ist = zoneinfo.ZoneInfo("Asia/Kolkata")
    except Exception:
        ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    return (
        (now_ist - timedelta(days=days)).strftime("%d-%m-%Y"),
        now_ist.strftime("%d-%m-%Y"),
    )


async def fetch_bulk_deals(company: str, days: int = 7) -> list[dict]:
    """Fetch bulk/block deals using nselib (legal, stable API wrapper)."""
    try:
        def _fetch():
            try:
                from nselib import capital_market
                from_date, to_date = _get_ist_dates(days)
                results = []

                # Try bulk deals
                try:
                    bulk_df = capital_market.bulk_deal_data(from_date=from_date, to_date=to_date)
                    if bulk_df is not None and not bulk_df.empty:
                        company_lower = company.lower()
                        for _, row in bulk_df.iterrows():
                            symbol = str(row.get("Symbol", row.get("SYMBOL", ""))).lower()
                            client = str(row.get("Client Name", row.get("CLIENT_NAME", ""))).lower()
                            if company_lower in symbol or company_lower in client:
                                results.append({
                                    "client": str(row.get("Client Name", row.get("CLIENT_NAME", ""))),
                                    "stock": str(row.get("Symbol", row.get("SYMBOL", ""))),
                                    "qty": int(row.get("Quantity Traded", row.get("QTY_TRADED", 0)) or 0),
                                    "price": float(row.get("Trade Price / Wt. Avg. Price", row.get("TRADE_PRICE", 0)) or 0),
                                    "side": str(row.get("Buy/Sell", row.get("BUY_SELL", ""))),
                                    "deal_type": "BULK",
                                })
                except Exception as e:
                    logger.warning(f"nselib bulk_deal_data error: {e}")

                # Try block deals
                try:
                    block_df = capital_market.block_deals_data(from_date=from_date, to_date=to_date)
                    if block_df is not None and not block_df.empty:
                        company_lower = company.lower()
                        for _, row in block_df.iterrows():
                            symbol = str(row.get("Symbol", row.get("SYMBOL", ""))).lower()
                            if company_lower in symbol:
                                results.append({
                                    "client": str(row.get("Client Name", row.get("CLIENT_NAME", ""))),
                                    "stock": str(row.get("Symbol", row.get("SYMBOL", ""))),
                                    "qty": int(row.get("Quantity Traded", row.get("QTY_TRADED", 0)) or 0),
                                    "price": float(row.get("Trade Price / Wt. Avg. Price", row.get("TRADE_PRICE", 0)) or 0),
                                    "side": "SELL",
                                    "deal_type": "BLOCK",
                                })
                except Exception as e:
                    logger.warning(f"nselib block_deals_data error: {e}")

                return results

            except ImportError:
                logger.warning("nselib not installed, bulk deals unavailable")
                return []
            except Exception as e:
                logger.error(f"nselib fetch error: {e}")
                return []

        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"fetch_bulk_deals error for {company}: {e}")
        return []


async def analyze_bulk_deal(deal: dict, market_price: float) -> dict:
    """
    Scenario 1: Analyze a bulk deal for distress signals.
    Returns enriched deal with distress probability and filing citation.
    """
    client = deal.get("client", "").lower()
    qty = deal.get("qty", 0)
    deal_price = deal.get("price", 0)
    side = deal.get("side", "").upper()

    # 1. Is this a promoter/insider?
    is_promoter = any(kw in client for kw in PROMOTER_KEYWORDS)

    # 2. Calculate discount/premium to market price
    if market_price > 0 and deal_price > 0:
        discount_pct = round(((market_price - deal_price) / market_price) * 100, 2)
    else:
        discount_pct = 0.0

    # 3. Distress probability scoring (0-100)
    distress_score = 0
    distress_reasons = []

    # Promoter selling = high signal
    if is_promoter and "sell" in side.lower():
        distress_score += 35
        distress_reasons.append("Promoter/insider identified as seller")

    # Significant discount (>3%) = concern
    if discount_pct > 3:
        distress_score += 25
        distress_reasons.append(f"Deal at {discount_pct:.1f}% discount to market price (₹{deal_price:,.0f} vs ₹{market_price:,.0f})")
    elif discount_pct > 1.5:
        distress_score += 15
        distress_reasons.append(f"Deal at {discount_pct:.1f}% discount to market")

    # Large volume = urgency
    if qty > 100000:
        distress_score += 15
        distress_reasons.append(f"Large quantity: {qty:,} shares traded")
    elif qty > 50000:
        distress_score += 10

    # Block deal at discount = worse
    if deal.get("deal_type") == "BLOCK" and discount_pct > 2:
        distress_score += 10
        distress_reasons.append("Block deal negotiated at discount - suggests urgency")

    # Cap at 100
    distress_score = min(distress_score, 100)

    # 4. Classification
    if distress_score >= 60:
        assessment = "LIKELY_DISTRESS"
        action = "REDUCE exposure / set tight stop-loss. Monitor for further promoter exits."
    elif distress_score >= 35:
        assessment = "ELEVATED_CONCERN"
        action = "INCREASE MONITORING. Watch for follow-up filings or management commentary."
    else:
        assessment = "ROUTINE_BLOCK"
        action = "No immediate action required. Likely portfolio rebalancing."

    # 5. Filing citation
    filing_citation = (
        f"NSE {deal.get('deal_type', 'Bulk')} Deal Filing: "
        f"{deal.get('client', 'Unknown')} {'sold' if 'sell' in side.lower() else 'traded'} "
        f"{qty:,} shares of {deal.get('stock', 'N/A')} "
        f"at ₹{deal_price:,.2f}/share "
        f"({'at {:.1f}% discount'.format(discount_pct) if discount_pct > 0 else 'at market price'})"
    )

    return {
        **deal,
        "is_promoter": is_promoter,
        "discount_pct": discount_pct,
        "distress_score": distress_score,
        "distress_assessment": assessment,
        "distress_reasons": distress_reasons,
        "recommended_action": action,
        "filing_citation": filing_citation,
    }


async def fetch_fii_dii_activity() -> dict:
    """Fetch FII/DII daily trading activity via NSE direct API (Scenario 2)."""
    try:
        def _fetch():
            import requests
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://www.nseindia.com/",
            }
            try:
                session = requests.Session()
                # First hit main page to get cookies
                session.get("https://www.nseindia.com", headers=headers, timeout=5)
                # Then fetch FII/DII data
                resp = session.get(
                    "https://www.nseindia.com/api/fiidiiTradeReact",
                    headers=headers, timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    result = {"raw_data": data, "summary": {}}
                    # Parse the response
                    for entry in data if isinstance(data, list) else []:
                        category = str(entry.get("category", "")).strip().upper()
                        buy = float(entry.get("buyValue", entry.get("buy_value", 0)) or 0)
                        sell = float(entry.get("sellValue", entry.get("sell_value", 0)) or 0)
                        net = buy - sell
                        if "FII" in category or "FPI" in category:
                            result["summary"]["fii_net_cr"] = round(net / 100, 2)  # Convert to Cr
                            result["summary"]["fii_sentiment"] = "BUYING" if net > 0 else "SELLING"
                        elif "DII" in category:
                            result["summary"]["dii_net_cr"] = round(net / 100, 2)
                            result["summary"]["dii_sentiment"] = "BUYING" if net > 0 else "SELLING"
                    if not result["summary"]:
                        result["summary"]["note"] = "FII/DII data structure unrecognized"
                    return result
                else:
                    logger.warning(f"NSE FII/DII API returned {resp.status_code}")
                    return {"raw_data": [], "summary": {"note": f"NSE API {resp.status_code}"}}
            except requests.exceptions.ConnectionError:
                return {"raw_data": [], "summary": {"note": "NSE not reachable"}}
            except Exception as e:
                logger.warning(f"FII/DII direct fetch error: {e}")
                return {"raw_data": [], "summary": {"error": str(e)}}
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"fetch_fii_dii_activity error: {e}")
        return {"raw_data": [], "summary": {}}


async def fetch_insider_trades(company: str) -> list[dict]:
    """Fetch insider trading data using nselib."""
    try:
        def _fetch():
            try:
                from nselib import capital_market
                from_date, to_date = _get_ist_dates(30)
                try:
                    data = capital_market.insider_trading(
                        from_date=from_date,
                        to_date=to_date,
                    )
                    if data is not None and not data.empty:
                        company_upper = company.upper()
                        filtered = data[data["SYMBOL"].str.contains(company_upper, na=False)]
                        return filtered.head(20).to_dict("records")
                except (AttributeError, TypeError):
                    pass
                return []
            except ImportError:
                return []
            except Exception as e:
                logger.error(f"insider trades error: {e}")
                return []
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"fetch_insider_trades error for {company}: {e}")
        return []


async def fetch_price_volume(tickers: list[str], days: int = 14) -> dict:
    """Fetch price and volume data for multiple tickers via yfinance.
    Enhanced with 52-week high proximity and breakout data."""
    try:
        def _fetch():
            results = {}
            ticker_str = " ".join([f"{t}.NS" for t in tickers])
            df = yf.download(ticker_str, period="1y", group_by="ticker", auto_adjust=True, progress=False)

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

                    # 52-week range
                    high_52w = float(close.tail(min(252, len(close))).max())
                    low_52w = float(close.tail(min(252, len(close))).min())
                    near_52w_low = current_price <= low_52w * 1.05
                    near_52w_high = current_price >= high_52w * 0.97

                    results[ticker] = {
                        "current_price": round(current_price, 2),
                        "volume_today": int(volume_today),
                        "volume_20d_avg": int(volume_20d_avg),
                        "volume_spike": volume_spike,
                        "volume_ratio": round(volume_today / volume_20d_avg, 2) if volume_20d_avg > 0 else 1.0,
                        "price_change_7d_pct": round(price_change_7d_pct, 2),
                        "above_200dma": above_200dma,
                        "near_52w_low": near_52w_low,
                        "near_52w_high": near_52w_high,
                        "high_52w": round(high_52w, 2),
                        "low_52w": round(low_52w, 2),
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


def get_sector_beta(sector: str) -> float:
    """Return approximate Nifty-relative beta for a sector."""
    return SECTOR_BETA.get(sector, 1.0)
