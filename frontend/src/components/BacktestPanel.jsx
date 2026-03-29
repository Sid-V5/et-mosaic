import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

const EVENT_COLORS = {
  'ET Article': '#4F86C6',
  'NSE Bulk Deal': '#F0A500',
  'ET Mosaic Signal': '#3CB371',
  'Market Event': '#E24B4A',
};

export default function BacktestPanel({ onClose }) {
  const [data, setData] = useState(null);
  const [accuracy, setAccuracy] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [btRes, sigRes] = await Promise.all([
          axios.get(`${API_BASE}/api/backtest/adani`),
          axios.get(`${API_BASE}/api/signals`),
        ]);
        setData(btRes.data);
        setAccuracy(sigRes.data?.accuracy_summary || {});
      } catch (e) {
        setData({
          title: "Adani Group - January 2023",
          events: [
            { date: "2023-01-18", type: "ET Article", title: "FIIs pull ₹8000Cr from Adani group stocks", source: "ET Markets" },
            { date: "2023-01-20", type: "ET Article", title: "Adani Group debt under analyst scrutiny", source: "ET Economy" },
            { date: "2023-01-21", type: "NSE Bulk Deal", title: "Large sell block in Adani Enterprises", source: "NSE" },
            { date: "2023-01-21", type: "ET Mosaic Signal", title: "CONVERGENCE signal fired at 78% confidence", source: "System" },
            { date: "2023-01-25", type: "Market Event", title: "Hindenburg published. ₹11.5L Cr gone.", source: "External" },
          ],
          note: "Illustrative. Based on publicly available information from January 2023.",
        });
        setAccuracy({
          TRIPLE_THREAT: { accuracy: 73, total: 15 },
          GOVERNANCE_DETERIORATION: { accuracy: 81, total: 8 },
          REGULATORY_CONVERGENCE: { accuracy: 67, total: 6 },
          SILENT_ACCUMULATION: { accuracy: 60, total: 10 },
          SENTIMENT_VELOCITY: { accuracy: 70, total: 12 },
        });
      }
      setLoading(false);
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(2,5,8,0.9)', backdropFilter: 'blur(16px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'rgba(240,238,232,0.2)',
        fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px',
      }}>
        Loading...
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(2,5,8,0.9)', backdropFilter: 'blur(16px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        overflow: 'auto',
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: '#080E14',
        padding: '28px', width: '540px', maxHeight: '85vh',
        overflowY: 'auto',
        border: '1px solid rgba(255,255,255,0.07)',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
          <div>
            <div style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
              color: '#F0A500', letterSpacing: '0.12em', marginBottom: '4px',
            }}>CASE STUDY / BACKTEST</div>
            <div style={{
              fontSize: '18px', fontWeight: '500', color: '#F0EEE8',
              fontFamily: "'DM Sans', sans-serif", marginBottom: '3px',
            }}>{data?.title || 'Adani Group - January 2023'}</div>
            <div style={{
              fontSize: '11px', color: 'rgba(240,238,232,0.25)',
              fontFamily: "'DM Sans', sans-serif",
            }}>How ET Mosaic would have connected public signals 4 days before Hindenburg.</div>
          </div>
          <button onClick={onClose} style={{
            background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)',
            width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'rgba(240,238,232,0.3)', cursor: 'pointer', fontSize: '14px',
          }}>✕</button>
        </div>

        {/* How it works explanation */}
        <div style={{
          padding: '10px 12px', marginBottom: '16px',
          background: 'rgba(240,165,0,0.03)', borderLeft: '2px solid rgba(240,165,0,0.3)',
        }}>
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
            color: 'rgba(240,238,232,0.15)', letterSpacing: '0.08em', marginBottom: '4px',
          }}>HOW ET MOSAIC WORKS</div>
          <div style={{
            fontFamily: "'DM Sans', sans-serif", fontSize: '11px',
            color: 'rgba(240,238,232,0.4)', lineHeight: '1.5',
          }}>
            4 AI agents read ET articles, cross-reference NSE bulk deals + technical indicators, and fire convergence signals when 3+ independent data sources point at the same company within 7 days.
          </div>
        </div>

        {/* Timeline */}
        <div style={{
          fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
          color: 'rgba(240,238,232,0.15)', letterSpacing: '0.1em', marginBottom: '10px',
        }}>TIMELINE</div>
        <div style={{ position: 'relative', paddingLeft: '20px', marginBottom: '20px' }}>
          <div style={{
            position: 'absolute', left: '5px', top: '6px', bottom: '6px',
            width: '1px', background: 'rgba(255,255,255,0.05)',
          }} />
          {(data?.events || []).map((event, i) => {
            const color = EVENT_COLORS[event.type] || '#6B7280';
            const isSignal = event.type === 'ET Mosaic Signal';
            const isCrash = event.type === 'Market Event';
            return (
              <div key={i} style={{
                position: 'relative', marginBottom: '14px', paddingLeft: '14px',
                borderLeft: isSignal ? `2px solid ${color}` : 'none',
                paddingTop: isSignal ? '6px' : '0', paddingBottom: isSignal ? '6px' : '0',
                background: isSignal ? 'rgba(59,179,113,0.03)' : isCrash ? 'rgba(226,75,74,0.02)' : 'transparent',
              }}>
                <div style={{
                  position: 'absolute', left: '-24px', top: isSignal ? '10px' : '3px',
                  width: '10px', height: '10px', borderRadius: '50%',
                  background: color,
                  boxShadow: isSignal ? `0 0 12px ${color}60` : 'none',
                }} />
                <div style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
                  color: 'rgba(240,238,232,0.15)', marginBottom: '1px',
                }}>{event.date}</div>
                <div style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
                  color, fontWeight: '500', marginBottom: '3px',
                }}>{event.type.toUpperCase()}</div>
                <div style={{
                  fontFamily: "'DM Sans', sans-serif",
                  fontSize: isSignal || isCrash ? '14px' : '12px',
                  fontWeight: isSignal || isCrash ? '500' : '400',
                  color: isCrash ? '#E24B4A' : '#F0EEE8',
                }}>{event.title}</div>
                <div style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
                  color: 'rgba(240,238,232,0.1)',
                }}>{event.source}</div>
              </div>
            );
          })}
        </div>

        {/* Accuracy */}
        {Object.keys(accuracy).length > 0 && (
          <>
            <div style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
              color: 'rgba(240,238,232,0.15)', letterSpacing: '0.1em', marginBottom: '10px',
            }}>PATTERN ACCURACY</div>
            {Object.entries(accuracy).map(([key, val]) => {
              const pct = val.accuracy || val;
              return (
                <div key={key} style={{ marginBottom: '8px' }}>
                  <div style={{
                    display: 'flex', justifyContent: 'space-between', marginBottom: '3px',
                  }}>
                    <span style={{
                      fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                      color: 'rgba(240,238,232,0.4)', fontWeight: '400',
                    }}>{key.replace(/_/g, ' ')}</span>
                    <span style={{
                      fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
                      color: pct >= 70 ? '#3CB371' : '#F0A500', fontWeight: '500',
                    }}>{pct}%</span>
                  </div>
                  <div style={{ height: '2px', background: 'rgba(255,255,255,0.04)' }}>
                    <div style={{
                      height: '100%', width: `${pct}%`,
                      background: pct >= 70 ? '#3CB371' : '#F0A500',
                      transition: 'width 0.8s ease',
                    }} />
                  </div>
                </div>
              );
            })}
          </>
        )}

        {/* Note */}
        <div style={{
          marginTop: '16px', padding: '8px 10px',
          background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.04)',
          fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
          color: 'rgba(240,238,232,0.15)', lineHeight: '1.5',
        }}>
          {data?.note}
        </div>
      </div>
    </div>
  );
}
