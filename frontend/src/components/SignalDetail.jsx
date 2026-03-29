import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

export default function SignalDetail({ selectedSignal, username = '' }) {
  const [takenActions, setTakenActions] = useState([]);

  useEffect(() => {
    if (!selectedSignal?.id || !username) { setTakenActions([]); return; }
    try {
      const key = `et_actions_${username}`;
      const existing = JSON.parse(localStorage.getItem(key) || '[]');
      setTakenActions(existing.filter(a => a.signal_id === selectedSignal.id).map(a => a.action_type));
    } catch { setTakenActions([]); }
  }, [selectedSignal?.id, username]);

  const handleAction = (actionType) => {
    if (!selectedSignal?.id) return;
    const key = `et_actions_${username}`;
    try {
      const existing = JSON.parse(localStorage.getItem(key) || '[]');
      if (!existing.some(a => a.signal_id === selectedSignal.id && a.action_type === actionType)) {
        existing.push({ signal_id: selectedSignal.id, action_type: actionType, timestamp: Date.now() });
        localStorage.setItem(key, JSON.stringify(existing));
      }
    } catch { /* ignore */ }
    setTakenActions(prev => [...new Set([...prev, actionType])]);
    axios.post(`${API_BASE}/api/action`, { signal_id: selectedSignal.id, action_type: actionType }).catch(() => {});
  };

  if (!selectedSignal) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', height: '100%', padding: '32px',
      }}>
        <div style={{
          fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px',
          color: 'rgba(240,238,232,0.12)', letterSpacing: '0.12em',
          textTransform: 'uppercase', marginBottom: '10px',
        }}>EVIDENCE CHAIN</div>
        <div style={{
          fontFamily: "'DM Sans', sans-serif", fontSize: '13px',
          color: 'rgba(240,238,232,0.3)', textAlign: 'center', maxWidth: '280px',
          lineHeight: '1.6',
        }}>
          Select a signal to view its underlying evidence layers, cross-source verification, and historical accuracy.
        </div>
      </div>
    );
  }

  const s = selectedSignal;
  const technical = s.technical || {};
  const priceData = s.price_data || {};
  const bulkDeals = s.bulk_deals || [];
  const similarity = s.similarity || 0;
  const sentimentVelocity = s.sentiment_velocity || 0;
  const marketConfirmation = s.market_data_confirmation || 0;

  // Determine if this signal has NSE data (Indian equity vs global macro)
  const hasNSEData = Boolean(
    (s.nse_tickers && s.nse_tickers.length > 0) ||
    technical.rsi || technical.rsi_signal || bulkDeals.length > 0 ||
    priceData.current_price
  );

  const sevColor = s.severity === 'high' ? '#E24B4A' : s.severity === 'medium' ? '#F0A500' : '#0EA5A0';

  // Dynamic section numbering
  let sectionCounter = 0;
  const nextSection = (text) => {
    sectionCounter++;
    return (
      <div style={{
        fontFamily: "'IBM Plex Mono', monospace", fontSize: '13px',
        color: '#F0A500', letterSpacing: '0.1em',
        textTransform: 'uppercase', marginTop: sectionCounter > 1 ? '16px' : '0',
        marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px',
      }}>
        <span style={{ fontWeight: '600' }}>0{sectionCounter}</span>
        <span style={{ color: 'rgba(240,238,232,0.55)' }}>{text}</span>
      </div>
    );
  };

  const dataRow = (label, value, color = 'rgba(240,238,232,0.8)') => (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '4px 0',
    }}>
      <span style={{
        fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px',
        color: 'rgba(240,238,232,0.5)', textTransform: 'uppercase', letterSpacing: '0.05em',
      }}>{label}</span>
      <span style={{
        fontFamily: "'IBM Plex Mono', monospace", fontSize: '13px',
        color, fontWeight: '500',
      }}>{value}</span>
    </div>
  );

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      overflowY: 'auto', padding: '14px',
    }}>
      {/* Header */}
      <div style={{ marginBottom: '10px' }}>
        <div style={{ display: 'flex', gap: '5px', marginBottom: '5px', alignItems: 'center' }}>
          <span style={{
            fontSize: '9px', fontWeight: '500', textTransform: 'uppercase',
            padding: '2px 6px',
            background: `${sevColor}15`, color: sevColor,
            fontFamily: "'IBM Plex Mono', monospace",
          }}>{s.severity}</span>
          <span style={{
            fontSize: '9px', fontWeight: '400', textTransform: 'uppercase',
            padding: '2px 6px', color: 'rgba(240,238,232,0.2)',
            fontFamily: "'IBM Plex Mono', monospace",
          }}>{s.signal_type?.replace(/_/g, ' ')}</span>
        </div>
        <div style={{
          fontSize: '17px', fontWeight: '600', color: '#F0EEE8',
          fontFamily: "'DM Sans', sans-serif", lineHeight: '1.35', marginBottom: '5px',
        }}>{s.headline}</div>
        <div style={{
          fontSize: '14px', color: 'rgba(240,238,232,0.55)', lineHeight: '1.5',
          fontFamily: "'DM Sans', sans-serif", fontWeight: '300',
        }}>{s.summary}</div>
      </div>

      {/* Confidence bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <div style={{ flex: 1, height: '3px', background: 'rgba(255,255,255,0.05)' }}>
          <div style={{
            height: '100%', width: `${s.confidence}%`,
            background: s.confidence > 70 ? '#E24B4A' : s.confidence > 50 ? '#F0A500' : '#0EA5A0',
          }} />
        </div>
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace", fontSize: '13px', color: '#F0A500',
          fontWeight: '600',
        }}>{s.confidence}%</span>
      </div>

      {/* 01 Analysis Chain - primary evidence layer */}
      {s.analysis_chain?.length > 0 && (
        <>
          {nextSection('ANALYSIS CHAIN')}
          <div style={{
            padding: '8px 10px', background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.05)',
          }}>
            {s.analysis_chain.map((step, i) => (
              <div key={i} style={{
                display: 'flex', gap: '8px', padding: '5px 0',
                borderBottom: i < s.analysis_chain.length - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none',
              }}>
                <div style={{
                  width: '22px', height: '22px', borderRadius: '50%',
                  background: 'rgba(14,165,160,0.15)', display: 'flex',
                  alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px',
                  color: '#0EA5A0', fontWeight: '700',
                }}>{step.step}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px',
                    color: '#0EA5A0', letterSpacing: '0.05em', marginBottom: '1px',
                  }}>{step.agent}</div>
                  <div style={{
                    fontFamily: "'DM Sans', sans-serif", fontSize: '12px',
                    color: 'rgba(240,238,232,0.7)', lineHeight: '1.4',
                  }}>{step.action}</div>
                  {step.detail && (
                    <div style={{
                      fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px',
                      color: 'rgba(240,238,232,0.35)', marginTop: '1px',
                    }}>{step.detail}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* 02 Signal Balance (conflicting signals) */}
      {s.conflicting_signals?.verdict && s.conflicting_signals.verdict !== 'NEUTRAL' && (
        <>
          {nextSection('SIGNAL BALANCE')}
          <div style={{
            padding: '8px 10px', background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.05)',
          }}>
            {/* Verdict badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
              <span style={{
                fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px',
                fontWeight: '600', letterSpacing: '0.08em',
                padding: '2px 8px',
                background: s.conflicting_signals.verdict === 'CONFLICTING' ? 'rgba(240,165,0,0.12)' :
                  s.conflicting_signals.verdict === 'BULLISH' ? 'rgba(60,179,113,0.12)' : 'rgba(226,75,74,0.12)',
                color: s.conflicting_signals.verdict === 'CONFLICTING' ? '#F0A500' :
                  s.conflicting_signals.verdict === 'BULLISH' ? '#3CB371' : '#E24B4A',
              }}>{s.conflicting_signals.verdict}</span>
              {s.conflicting_signals.balance_note && (
                <span style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px',
                  color: 'rgba(240,238,232,0.35)',
                }}>{s.conflicting_signals.balance_note}</span>
              )}
            </div>

            {/* Bullish */}
            {s.conflicting_signals.bullish?.length > 0 && (
              <div style={{ marginBottom: '6px' }}>
                <div style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                  color: '#3CB371', letterSpacing: '0.06em', marginBottom: '3px',
                }}>BULLISH</div>
                {s.conflicting_signals.bullish.map((sig, i) => (
                  <div key={i} style={{
                    fontFamily: "'DM Sans', sans-serif", fontSize: '12px',
                    color: 'rgba(240,238,232,0.55)', padding: '2px 0 2px 10px',
                    borderLeft: '2px solid rgba(60,179,113,0.25)',
                  }}>{sig}</div>
                ))}
              </div>
            )}

            {/* Bearish */}
            {s.conflicting_signals.bearish?.length > 0 && (
              <div>
                <div style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                  color: '#E24B4A', letterSpacing: '0.06em', marginBottom: '3px',
                }}>BEARISH</div>
                {s.conflicting_signals.bearish.map((sig, i) => (
                  <div key={i} style={{
                    fontFamily: "'DM Sans', sans-serif", fontSize: '12px',
                    color: 'rgba(240,238,232,0.55)', padding: '2px 0 2px 10px',
                    borderLeft: '2px solid rgba(226,75,74,0.25)',
                  }}>{sig}</div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* 03 Market Data + Technical (only for NSE equities) */}
      {hasNSEData && (
        <>
          {nextSection('MARKET VERIFICATION')}
          <div style={{
            padding: '8px 10px', background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.05)',
          }}>
            {/* Bulk Deals */}
            {bulkDeals.length > 0 && (
              <>
                <div style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                  color: 'rgba(240,238,232,0.3)', letterSpacing: '0.06em', marginBottom: '4px',
                }}>BULK/BLOCK DEALS</div>
                {bulkDeals.slice(0, 3).map((deal, i) => (
                  <div key={i} style={{
                    padding: '5px 0',
                    borderBottom: i < Math.min(bulkDeals.length, 3) - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{
                        fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px',
                        color: 'rgba(240,238,232,0.7)',
                      }}>{deal.client || deal.stock}</span>
                      {deal.distress_assessment && (
                        <span style={{
                          fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                          fontWeight: '600', padding: '1px 6px', letterSpacing: '0.04em',
                          background: deal.distress_assessment === 'LIKELY_DISTRESS' ? 'rgba(226,75,74,0.15)' :
                            deal.distress_assessment === 'ELEVATED_CONCERN' ? 'rgba(240,165,0,0.12)' : 'rgba(60,179,113,0.1)',
                          color: deal.distress_assessment === 'LIKELY_DISTRESS' ? '#E24B4A' :
                            deal.distress_assessment === 'ELEVATED_CONCERN' ? '#F0A500' : '#3CB371',
                        }}>{deal.distress_assessment?.replace(/_/g, ' ')}</span>
                      )}
                    </div>
                    <div style={{
                      fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px',
                      color: 'rgba(240,238,232,0.45)', marginTop: '2px',
                    }}>
                      {deal.qty?.toLocaleString()} shares @ {'\u20B9'}{deal.price?.toLocaleString()} {'\u2022'} {deal.side}
                      {deal.discount_pct > 0 && (
                        <span style={{ color: '#E24B4A', fontWeight: '600' }}> {'\u2022'} {deal.discount_pct}% discount</span>
                      )}
                      {deal.is_promoter && (
                        <span style={{ color: '#F0A500' }}> {'\u2022'} PROMOTER</span>
                      )}
                    </div>
                    {deal.recommended_action && (
                      <div style={{
                        fontFamily: "'DM Sans', sans-serif", fontSize: '11px',
                        color: 'rgba(240,238,232,0.4)', marginTop: '3px', fontStyle: 'italic',
                      }}>{'\u2192'} {deal.recommended_action}</div>
                    )}
                  </div>
                ))}
              </>
            )}

            {/* Technical Indicators */}
            {(technical.rsi_signal || technical.rsi) && (
              <>
                {bulkDeals.length > 0 && <div style={{ borderTop: '1px solid rgba(255,255,255,0.04)', margin: '6px 0' }} />}
                <div style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                  color: 'rgba(240,238,232,0.3)', letterSpacing: '0.06em', marginBottom: '4px',
                }}>TECHNICAL INDICATORS</div>

                {/* 52-Week Breakout highlight */}
                {technical.breakout_52w && (
                  <div style={{
                    padding: '6px 8px', marginBottom: '6px',
                    background: technical.volume_confirmed ? 'rgba(60,179,113,0.08)' : 'rgba(240,165,0,0.06)',
                    border: `1px solid ${technical.volume_confirmed ? 'rgba(60,179,113,0.2)' : 'rgba(240,165,0,0.15)'}`,
                  }}>
                    <div style={{
                      fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px',
                      fontWeight: '700', color: technical.volume_confirmed ? '#3CB371' : '#F0A500',
                      marginBottom: '3px',
                    }}>
                      52-WEEK HIGH BREAKOUT {technical.volume_confirmed ? '(VOL CONFIRMED)' : '(UNCONFIRMED)'}
                    </div>
                    {dataRow('52W High', `\u20B9${technical.high_52w?.toLocaleString()}`, '#3CB371')}
                    {dataRow('Volume Ratio', `${technical.volume_ratio}x avg`, technical.volume_ratio > 1.5 ? '#3CB371' : '#F0A500')}
                    {technical.pattern_success_rate?.sample_size > 0 && (
                      <>
                        {dataRow('T+5 Win Rate', `${technical.pattern_success_rate.t5_win_rate}%`,
                          technical.pattern_success_rate.t5_win_rate > 60 ? '#3CB371' : '#F0A500')}
                        {dataRow('T+20 Win Rate', `${technical.pattern_success_rate.t20_win_rate}%`,
                          technical.pattern_success_rate.t20_win_rate > 55 ? '#3CB371' : '#F0A500')}
                        <div style={{
                          fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                          color: 'rgba(240,238,232,0.3)', marginTop: '2px',
                        }}>{technical.pattern_success_rate.note}</div>
                      </>
                    )}
                  </div>
                )}

                {dataRow('RSI (14)', `${Number(technical.rsi || technical.RSI_14).toFixed(1)} ${technical.rsi_signal || ''}`,
                  technical.rsi_signal === 'OVERBOUGHT' ? '#E24B4A' : technical.rsi_signal === 'OVERSOLD' ? '#3CB371' : 'rgba(240,238,232,0.7)')}
                {technical.macd_class && dataRow('MACD', technical.macd_class?.replace(/_/g, ' '),
                  technical.macd_class === 'BEARISH_CROSS' ? '#E24B4A' : '#3CB371')}
                {technical.dma_signal && dataRow('200-DMA', technical.dma_signal?.replace(/_/g, ' '),
                  technical.dma_signal === 'BELOW_200DMA' ? '#E24B4A' : '#3CB371')}
                {technical.golden_cross && dataRow('Cross', 'Golden Cross (50 > 200 DMA)', '#3CB371')}
                {technical.death_cross && dataRow('Cross', 'Death Cross (50 < 200 DMA)', '#E24B4A')}

                {/* FII/DII Activity */}
                {technical.fii_dii && (
                  <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                    <div style={{
                      fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                      color: 'rgba(240,238,232,0.3)', letterSpacing: '0.06em', marginBottom: '3px',
                    }}>INSTITUTIONAL FLOW</div>
                    {technical.fii_dii.fii_sentiment && dataRow('FII/FPI',
                      `${technical.fii_dii.fii_sentiment} (\u20B9${Math.abs(technical.fii_dii.fii_net_cr || 0).toFixed(0)} Cr)`,
                      technical.fii_dii.fii_sentiment === 'BUYING' ? '#3CB371' : '#E24B4A')}
                    {technical.fii_dii.dii_sentiment && dataRow('DII',
                      `${technical.fii_dii.dii_sentiment} (\u20B9${Math.abs(technical.fii_dii.dii_net_cr || 0).toFixed(0)} Cr)`,
                      technical.fii_dii.dii_sentiment === 'BUYING' ? '#3CB371' : '#E24B4A')}
                  </div>
                )}
              </>
            )}

            {/* Contagion info */}
            {(s.contagion_type && s.contagion_type !== 'isolated') && (
              <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                <div style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                  color: 'rgba(240,238,232,0.3)', letterSpacing: '0.06em', marginBottom: '3px',
                }}>CONTAGION</div>
                {dataRow('Type', s.contagion_type.toUpperCase(),
                  s.contagion_type === 'systemic' ? '#E24B4A' : '#F0A500')}
                {s.affected_peers?.length > 0 && (
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '4px' }}>
                    {s.affected_peers.map((peer, i) => (
                      <span key={i} style={{
                        fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                        color: 'rgba(240,238,232,0.4)', padding: '2px 6px',
                        background: 'rgba(255,255,255,0.03)',
                      }}>{peer}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Price data rows */}
            {priceData.volume_spike && dataRow('Volume Spike', 'Detected', '#E24B4A')}
            {priceData.price_change_7d_pct != null && dataRow('7D Change', `${priceData.price_change_7d_pct?.toFixed(1)}%`,
              priceData.price_change_7d_pct < -5 ? '#E24B4A' : 'rgba(240,238,232,0.7)')}
          </div>
        </>
      )}

      {/* 04 Portfolio Impact */}
      {s.portfolio_impact?.materiality && s.portfolio_impact.materiality !== 'NONE' && (
        <>
          {nextSection('PORTFOLIO IMPACT')}
          <div style={{
            padding: '10px', background: s.portfolio_impact.materiality === 'HIGH'
              ? 'rgba(226,75,74,0.06)' : 'rgba(240,165,0,0.04)',
            border: `1px solid ${s.portfolio_impact.materiality === 'HIGH'
              ? 'rgba(226,75,74,0.2)' : 'rgba(240,165,0,0.15)'}`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{
                fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px',
                color: s.portfolio_impact.materiality === 'HIGH' ? '#E24B4A' : '#F0A500',
                fontWeight: '600', letterSpacing: '0.06em',
              }}>{s.portfolio_impact.materiality} MATERIALITY</span>
              <span style={{
                fontFamily: "'IBM Plex Mono', monospace", fontSize: '14px',
                color: s.portfolio_impact.total_impact_inr < 0 ? '#E24B4A' : '#3CB371',
                fontWeight: '700',
              }}>
                {s.portfolio_impact.total_impact_inr < 0 ? '\u2212' : '+'}{'\u20B9'}{Math.abs(s.portfolio_impact.total_impact_inr || 0).toLocaleString('en-IN')}
              </span>
            </div>
            {dataRow('Portfolio Impact', `${s.portfolio_impact.total_impact_pct || 0}%`,
              Math.abs(s.portfolio_impact.total_impact_pct) >= 2 ? '#E24B4A' : '#F0A500')}
            {s.portfolio_impact.affected_holdings?.map((h, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', padding: '3px 0',
                borderTop: '1px solid rgba(255,255,255,0.03)',
              }}>
                <span style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px',
                  color: 'rgba(240,238,232,0.6)',
                }}>{h.ticker}</span>
                <span style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px',
                  color: h.estimated_impact_inr < 0 ? '#E24B4A' : '#3CB371',
                }}>
                  {h.estimated_impact_inr < 0 ? '\u2212' : '+'}{'\u20B9'}{Math.abs(h.estimated_impact_inr).toLocaleString('en-IN')} ({h.estimated_impact_pct}%)
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* 05 Source Citations */}
      {s.filing_citation?.length > 0 && (
        <>
          {nextSection('SOURCE CITATIONS')}
          <div style={{
            padding: '8px 10px', background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.05)',
          }}>
            {s.filing_citation.map((citation, i) => (
              <div key={i} style={{
                fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px',
                color: 'rgba(240,238,232,0.55)', padding: '4px 0 4px 8px',
                borderLeft: '2px solid rgba(79,134,198,0.3)', marginBottom: '4px',
                lineHeight: '1.4',
              }}>
                <span style={{ color: 'rgba(79,134,198,0.8)' }}>{'\uD83D\uDCC4'} </span>
                {citation}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Recommendation + Actions */}
      {nextSection('RECOMMENDATION')}
      {s.action_recommendation?.reasoning && (
        <div style={{
          fontFamily: "'DM Sans', sans-serif", fontSize: '13px',
          color: 'rgba(240,238,232,0.55)', marginBottom: '8px', lineHeight: '1.5',
        }}>{s.action_recommendation.reasoning}</div>
      )}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '10px' }}>
        {['ADD_WATCHLIST', 'REDUCE_EXPOSURE', 'INCREASE_MONITORING'].map(action => {
          const isTaken = takenActions.includes(action);
          const colors = { ADD_WATCHLIST: '#0EA5A0', REDUCE_EXPOSURE: '#E24B4A', INCREASE_MONITORING: '#F0A500' };
          const labels = { ADD_WATCHLIST: 'WATCHLIST', REDUCE_EXPOSURE: 'REDUCE', INCREASE_MONITORING: 'MONITOR' };
          return (
            <button
              key={action}
              onClick={() => handleAction(action)}
              style={{
                flex: 1, padding: '7px', border: 'none', cursor: 'pointer',
                fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                fontWeight: '500', letterSpacing: '0.06em',
                background: isTaken ? `${colors[action]}20` : 'rgba(255,255,255,0.04)',
                color: isTaken ? colors[action] : 'rgba(240,238,232,0.45)',
                borderBottom: isTaken ? `2px solid ${colors[action]}` : '2px solid transparent',
                transition: 'all 0.2s ease',
              }}
            >
              {isTaken ? '\u2713 ' : ''}{labels[action]}
            </button>
          );
        })}
      </div>

      {/* What to Watch */}
      {s.what_to_watch && (
        <div style={{
          padding: '8px 10px',
          background: 'rgba(240,165,0,0.03)', borderLeft: '2px solid rgba(240,165,0,0.3)',
          marginBottom: '10px',
        }}>
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
            color: 'rgba(240,238,232,0.2)', letterSpacing: '0.08em', marginBottom: '4px',
          }}>WATCH</div>
          <div style={{
            fontFamily: "'DM Sans', sans-serif", fontSize: '13px',
            color: 'rgba(240,238,232,0.6)', lineHeight: '1.5',
          }}>{s.what_to_watch}</div>
        </div>
      )}

      {/* Audio Brief */}
      {s.audio_path && (
        <div style={{
          background: '#0D1117',
          border: '1px solid rgba(240,165,0,0.15)',
          padding: '10px 12px', marginBottom: '8px',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px',
          }}>
            <span style={{
              width: '5px', height: '5px', borderRadius: '50%',
              background: '#F0A500', flexShrink: 0,
            }} />
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
              letterSpacing: '0.1em', color: '#F0A500',
            }}>AUDIO BRIEF</span>
          </div>
          <audio
            controls
            src={`${API_BASE}/api/signal/${s.id}/audio`}
            style={{
              width: '100%', height: '32px',
              filter: 'invert(85%) hue-rotate(180deg) contrast(1.5) brightness(1.2)',
              borderRadius: 0,
            }}
          />
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
            color: 'rgba(240,238,232,0.15)', marginTop: '4px',
          }}>
            Orpheus TTS via Groq
          </div>
        </div>
      )}
    </div>
  );
}
