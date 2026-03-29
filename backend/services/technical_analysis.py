"""
Technical Analysis Service — Enhanced for ET Hackathon Scenario 2.
Detects: RSI, MACD, BBands, 200-DMA, 52-week breakouts, golden/death crosses.
Computes: historical pattern success rate, conflicting signals analysis.
No LLM — purely pandas-ta + numpy computations.
"""

import asyncio
import logging
import numpy as np
import yfinance as yf
import pandas_ta as ta

logger = logging.getLogger(__name__)


class TechnicalAnalysisService:

    async def analyse(self, ticker: str) -> dict:
        """Run full technical analysis on an NSE ticker with breakout detection."""
        try:
            def _analyse():
                # 1y data for proper 200-DMA & 52-week high calculations
                df = yf.download(f"{ticker}.NS", period="1y", progress=False, auto_adjust=True)

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
                close_series = df["Close"].dropna()
                volume_series = df["Volume"].dropna()
                price = float(latest["Close"])

                # ── Core indicators ──
                rsi = float(latest.get("RSI_14", 50))
                macd = float(latest.get("MACD_12_26_9", 0))
                macd_signal = float(latest.get("MACDs_12_26_9", 0))
                bbl = float(latest.get("BBL_20_2.0", 0))
                bbu = float(latest.get("BBU_20_2.0", 0))
                sma_50 = float(latest.get("SMA_50", 0))
                sma_200 = float(latest.get("SMA_200", 0))
                atr = float(latest.get("ATRr_14", 0))

                # ── Signal classifications ──
                rsi_signal = "OVERBOUGHT" if rsi > 70 else ("OVERSOLD" if rsi < 30 else "NEUTRAL")
                macd_class = "BEARISH_CROSS" if macd < macd_signal else "BULLISH_CROSS"
                bb_signal = "SQUEEZE_LOW" if price < bbl else ("SQUEEZE_HIGH" if price > bbu else "NEUTRAL")
                dma_signal = "BELOW_200DMA" if (sma_200 > 0 and price < sma_200) else "ABOVE_200DMA"

                # ── 52-Week High Breakout Detection (Scenario 2) ──
                high_52w = float(close_series.tail(min(252, len(close_series))).max())
                low_52w = float(close_series.tail(min(252, len(close_series))).min())
                breakout_52w = price >= high_52w * 0.99  # within 1% of 52w high = breakout

                # Volume confirmation for breakout
                vol_today = float(volume_series.iloc[-1]) if len(volume_series) > 0 else 0
                vol_20d_avg = float(volume_series.tail(20).mean()) if len(volume_series) >= 20 else float(volume_series.mean())
                vol_ratio = round(vol_today / vol_20d_avg, 2) if vol_20d_avg > 0 else 1.0
                volume_confirmed = vol_ratio > 1.5  # breakout on >150% avg volume

                # ── Golden/Death Cross ──
                golden_cross = sma_50 > sma_200 > 0
                death_cross = sma_200 > sma_50 > 0

                # ── Historical Pattern Success Rate (backtest) ──
                success_rate = self._calculate_breakout_success_rate(close_series, volume_series)

                # ── Conflicting Signals Analysis ──
                bullish_signals = []
                bearish_signals = []

                if breakout_52w:
                    bullish_signals.append(f"52-week high breakout at ₹{price:,.0f}")
                if volume_confirmed:
                    bullish_signals.append(f"Volume {vol_ratio:.1f}x above 20-day avg (strong conviction)")
                if macd_class == "BULLISH_CROSS":
                    bullish_signals.append(f"MACD bullish crossover ({macd:.4f} > {macd_signal:.4f})")
                if golden_cross:
                    bullish_signals.append("Golden cross (50-DMA > 200-DMA)")
                if dma_signal == "ABOVE_200DMA":
                    bullish_signals.append(f"Trading above 200-DMA (₹{sma_200:,.0f})")
                if rsi_signal == "OVERSOLD":
                    bullish_signals.append(f"RSI oversold at {rsi:.0f} - potential bounce")

                if rsi_signal == "OVERBOUGHT":
                    bearish_signals.append(f"RSI overbought at {rsi:.0f} - momentum exhaustion risk")
                if macd_class == "BEARISH_CROSS":
                    bearish_signals.append(f"MACD bearish crossover ({macd:.4f} < {macd_signal:.4f})")
                if death_cross:
                    bearish_signals.append("Death cross (50-DMA < 200-DMA)")
                if dma_signal == "BELOW_200DMA":
                    bearish_signals.append(f"Trading below 200-DMA (₹{sma_200:,.0f})")
                if bb_signal == "SQUEEZE_HIGH":
                    bearish_signals.append("Above upper Bollinger Band - extended territory")
                if not volume_confirmed and breakout_52w:
                    bearish_signals.append(f"Breakout on weak volume ({vol_ratio:.1f}x avg) - false breakout risk")

                # ── Risk score ──
                tech_score = 0
                if rsi_signal == "OVERBOUGHT": tech_score += 1
                if macd_class == "BEARISH_CROSS": tech_score += 1
                if dma_signal == "BELOW_200DMA": tech_score += 1
                if not volume_confirmed and breakout_52w: tech_score += 1
                confirms_risk = tech_score >= 2

                # ── Pattern summary ──
                pattern = "NONE"
                if breakout_52w and volume_confirmed:
                    pattern = "52W_HIGH_BREAKOUT_CONFIRMED"
                elif breakout_52w and not volume_confirmed:
                    pattern = "52W_HIGH_BREAKOUT_UNCONFIRMED"
                elif price <= low_52w * 1.05:
                    pattern = "NEAR_52W_LOW"

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
                    # NEW: Scenario 2 fields
                    "high_52w": round(high_52w, 2),
                    "low_52w": round(low_52w, 2),
                    "breakout_52w": breakout_52w,
                    "volume_ratio": vol_ratio,
                    "volume_confirmed": volume_confirmed,
                    "golden_cross": golden_cross,
                    "death_cross": death_cross,
                    "pattern": pattern,
                    "pattern_success_rate": success_rate,
                    "bullish_signals": bullish_signals,
                    "bearish_signals": bearish_signals,
                    "conflicting": len(bullish_signals) > 0 and len(bearish_signals) > 0,
                }

            return await asyncio.to_thread(_analyse)

        except Exception as e:
            logger.error(f"Technical analysis error for {ticker}: {e}")
            return {
                "ticker": ticker,
                "error": str(e),
                "confirms_risk": False,
            }

    @staticmethod
    def _calculate_breakout_success_rate(close_series, volume_series, lookback: int = 252) -> dict:
        """
        Backtest: When this stock broke its rolling 60-day high on above-avg volume,
        what % of the time did it continue up T+5, T+10, T+20?
        Returns historical success metrics.
        """
        try:
            if len(close_series) < 60:
                return {"t5_win_rate": 0, "t10_win_rate": 0, "t20_win_rate": 0, "sample_size": 0}

            closes = close_series.values.flatten() if hasattr(close_series.values, 'flatten') else np.array(close_series.values)
            vols = volume_series.values.flatten() if hasattr(volume_series.values, 'flatten') else np.array(volume_series.values)

            wins_t5 = 0
            wins_t10 = 0
            wins_t20 = 0
            total = 0

            # Scan for historical breakout points
            for i in range(60, min(len(closes) - 20, lookback)):
                rolling_high = np.max(closes[max(0, i-60):i])
                avg_vol = np.mean(vols[max(0, i-20):i])

                # Breakout: close above rolling 60d high on above-avg volume
                if closes[i] > rolling_high and avg_vol > 0 and vols[i] > avg_vol * 1.3:
                    total += 1
                    if i + 5 < len(closes) and closes[i + 5] > closes[i]:
                        wins_t5 += 1
                    if i + 10 < len(closes) and closes[i + 10] > closes[i]:
                        wins_t10 += 1
                    if i + 20 < len(closes) and closes[i + 20] > closes[i]:
                        wins_t20 += 1

            return {
                "t5_win_rate": round((wins_t5 / total * 100), 0) if total > 0 else 0,
                "t10_win_rate": round((wins_t10 / total * 100), 0) if total > 0 else 0,
                "t20_win_rate": round((wins_t20 / total * 100), 0) if total > 0 else 0,
                "sample_size": total,
                "note": f"Based on {total} breakout events in last {lookback} trading days"
            }
        except Exception as e:
            logger.warning(f"Breakout success rate calc error: {e}")
            return {"t5_win_rate": 0, "t10_win_rate": 0, "t20_win_rate": 0, "sample_size": 0}
