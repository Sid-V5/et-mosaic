"""
Technical Analysis Service — deterministic RSI, MACD, Bollinger Bands, DMA.
No LLM — purely pandas-ta computations.
"""

import asyncio
import logging
import yfinance as yf
import pandas_ta as ta

logger = logging.getLogger(__name__)


class TechnicalAnalysisService:

    async def analyse(self, ticker: str) -> dict:
        """Run full technical analysis on an NSE ticker."""
        try:
            def _analyse():
                df = yf.download(f"{ticker}.NS", period="90d", progress=False, auto_adjust=True)

                # Flatten multi-level columns if present
                if hasattr(df.columns, 'levels') and df.columns.nlevels > 1:
                    df.columns = df.columns.get_level_values(0)

                if df is None or len(df) < 30:
                    return {
                        "ticker": ticker,
                        "error": "insufficient_data",
                        "confirms_risk": False,
                    }

                # Run pandas-ta strategy
                df.ta.strategy(ta.Strategy(
                    name="mosaic",
                    ta=[
                        {"kind": "rsi", "length": 14},
                        {"kind": "macd", "fast": 12, "slow": 26, "signal": 9},
                        {"kind": "bbands", "length": 20},
                        {"kind": "sma", "length": 50},
                        {"kind": "sma", "length": 200},
                        {"kind": "atr", "length": 14},
                    ]
                ))

                latest = df.iloc[-1]

                # Extract values safely
                rsi = float(latest.get("RSI_14", 50))
                macd = float(latest.get("MACD_12_26_9", 0))
                macd_signal = float(latest.get("MACDs_12_26_9", 0))
                bbl = float(latest.get("BBL_20_2.0", 0))
                bbu = float(latest.get("BBU_20_2.0", 0))
                sma_50 = float(latest.get("SMA_50", 0))
                sma_200 = float(latest.get("SMA_200", 0))
                atr = float(latest.get("ATRr_14", 0))
                price = float(latest["Close"])

                # Classify signals
                if rsi > 70:
                    rsi_signal = "OVERBOUGHT"
                elif rsi < 30:
                    rsi_signal = "OVERSOLD"
                else:
                    rsi_signal = "NEUTRAL"

                macd_class = "BEARISH_CROSS" if macd < macd_signal else "BULLISH_CROSS"

                if price < bbl:
                    bb_signal = "SQUEEZE_LOW"
                elif price > bbu:
                    bb_signal = "SQUEEZE_HIGH"
                else:
                    bb_signal = "NEUTRAL"

                dma_signal = "BELOW_200DMA" if price < sma_200 else "ABOVE_200DMA"

                # Tech risk score: each bearish indicator adds 1
                tech_score = 0
                if rsi_signal == "OVERBOUGHT":
                    tech_score += 1
                if macd_class == "BEARISH_CROSS":
                    tech_score += 1
                if dma_signal == "BELOW_200DMA":
                    tech_score += 1

                confirms_risk = tech_score >= 2

                return {
                    "ticker": ticker,
                    "price": round(price, 2),
                    "rsi": round(rsi, 2),
                    "rsi_signal": rsi_signal,
                    "macd": round(macd, 4),
                    "macd_signal_line": round(macd_signal, 4),
                    "macd_class": macd_class,
                    "bb_lower": round(bbl, 2),
                    "bb_upper": round(bbu, 2),
                    "bb_signal": bb_signal,
                    "sma_50": round(sma_50, 2),
                    "sma_200": round(sma_200, 2),
                    "dma_signal": dma_signal,
                    "atr": round(atr, 2),
                    "tech_score": tech_score,
                    "confirms_risk": confirms_risk,
                }

            return await asyncio.to_thread(_analyse)

        except Exception as e:
            logger.error(f"Technical analysis error for {ticker}: {e}")
            return {
                "ticker": ticker,
                "error": str(e),
                "confirms_risk": False,
            }
