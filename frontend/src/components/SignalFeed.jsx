import { useState, useEffect } from 'react';

export default function SignalFeed({
  signals = [], allSignalsLoaded = false, onSignalClick,
  selectedSignalId, username = '',
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  // Get saved actions for this user
  const getSavedActions = (signalId) => {
    try {
      const existing = JSON.parse(localStorage.getItem(`et_actions_${username}`) || '[]');
      return existing.filter(a => a.signal_id === signalId).map(a => a.action_type);
    } catch { return []; }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Signal Cards */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 10px' }}>
        {/* Empty state: only show when backend hasn't sent any signals ever */}
        {signals.length === 0 && !allSignalsLoaded && (
          <EmptyState />
        )}

        {/* Filtered-out state: signals exist but all are below threshold */}
        {signals.length === 0 && allSignalsLoaded && (
          <div style={{
            padding: '24px 12px', textAlign: 'center',
          }}>
            <div style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px',
              color: 'rgba(240,238,232,0.2)', letterSpacing: '0.08em',
            }}>
              No signals above this confidence threshold.
            </div>
          </div>
        )}

        {signals.map((signal, index) => {
          const isSelected = selectedSignalId === signal.id;
          const savedActions = getSavedActions(signal.id);
          const hasActions = savedActions.length > 0;

          const sevStyles = {
            high: { bg: 'rgba(226,75,74,0.08)', color: '#E24B4A', border: 'rgba(226,75,74,0.2)' },
            medium: { bg: 'rgba(240,165,0,0.08)', color: '#F0A500', border: 'rgba(240,165,0,0.2)' },
            low: { bg: 'rgba(14,165,160,0.08)', color: '#0EA5A0', border: 'rgba(14,165,160,0.2)' },
          };
          const severity = sevStyles[signal.severity] || sevStyles.low;

          return (
            <div
              key={signal.id || index}
              onClick={() => onSignalClick?.(signal)}
              style={{
                background: isSelected ? 'rgba(240,165,0,0.04)' : 'rgba(255,255,255,0.015)',
                border: isSelected ? '1px solid rgba(240,165,0,0.2)' : '1px solid rgba(255,255,255,0.04)',
                padding: '12px',
                marginBottom: '6px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                opacity: mounted ? 1 : 0,
                transform: mounted ? 'translateY(0)' : 'translateY(8px)',
                transitionDelay: `${index * 50}ms`,
              }}
            >
              {/* Badges */}
              <div style={{ display: 'flex', gap: '4px', marginBottom: '5px', flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{
                  fontSize: '9px', fontWeight: '500', textTransform: 'uppercase',
                  padding: '2px 6px', letterSpacing: '0.06em',
                  background: severity.bg, color: severity.color,
                  fontFamily: "'IBM Plex Mono', monospace",
                }}>
                  {signal.severity}
                </span>
                {signal.freshness === 'BREAKING' && (
                  <span style={{
                    fontSize: '8px', fontWeight: '500', textTransform: 'uppercase',
                    padding: '1px 5px', letterSpacing: '0.06em',
                    background: 'rgba(226,75,74,0.1)', color: '#E24B4A',
                    fontFamily: "'IBM Plex Mono', monospace",
                    animation: 'pulse 1.5s ease-in-out infinite',
                  }}>
                    BREAKING
                  </span>
                )}
                {signal.portfolio_relevance === 'direct' && (
                  <span style={{
                    fontSize: '8px', fontWeight: '500', padding: '1px 5px',
                    background: 'rgba(240,165,0,0.08)', color: '#F0A500',
                    fontFamily: "'IBM Plex Mono', monospace",
                  }}>
                    PORTFOLIO
                  </span>
                )}
                {hasActions && (
                  <span style={{
                    fontSize: '8px', fontWeight: '500', padding: '1px 5px',
                    background: 'rgba(59,179,113,0.08)', color: '#3CB371',
                    fontFamily: "'IBM Plex Mono', monospace",
                  }}>
                    {savedActions.length} ACTION{savedActions.length > 1 ? 'S' : ''}
                  </span>
                )}
                <span style={{
                  fontSize: '8px', fontWeight: '400', padding: '1px 5px',
                  color: 'rgba(240,238,232,0.15)',
                  fontFamily: "'IBM Plex Mono', monospace", marginLeft: 'auto',
                }}>
                  {signal.signal_type?.replace(/_/g, ' ')}
                </span>
              </div>

              {/* Headline */}
              <div style={{
                fontWeight: '500', color: '#F0EEE8', fontSize: '15px', marginBottom: '4px',
                fontFamily: "'DM Sans', sans-serif", lineHeight: '1.3',
              }}>
                {signal.headline}
              </div>

              {/* Summary */}
              <div style={{
                color: 'rgba(240,238,232,0.45)', fontSize: '13px', lineHeight: '1.4', marginBottom: '6px',
                fontFamily: "'DM Sans', sans-serif", fontWeight: '300',
              }}>
                {signal.summary?.slice(0, 120)}{signal.summary?.length > 120 ? '...' : ''}
              </div>

              {/* Confidence Bar */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <div style={{ flex: 1, height: '2px', background: 'rgba(255,255,255,0.04)' }}>
                  <div style={{
                    height: '100%',
                    width: `${signal.confidence}%`,
                    background: signal.confidence > 70 ? '#E24B4A' : signal.confidence > 50 ? '#F0A500' : '#0EA5A0',
                    transition: 'width 0.5s ease',
                  }} />
                </div>
                <span style={{
                  fontSize: '9px', color: '#F0A500', fontWeight: '500',
                  fontFamily: "'IBM Plex Mono', monospace", minWidth: '28px', textAlign: 'right',
                }}>{signal.confidence}%</span>
              </div>
            </div>
          );
        })}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}

/* Empty state - shown only when backend hasn't loaded signals yet */
function EmptyState() {
  const events = [
    { date: 'Jan 18', color: '#4F86C6', badge: 'ET MARKETS', title: 'FIIs pull ₹8,000 Cr from Adani stocks' },
    { date: 'Jan 20', color: '#4F86C6', badge: 'ET ECONOMY', title: 'Adani debt under scrutiny' },
    { date: 'Jan 21', color: '#F0A500', badge: 'NSE', title: 'Large block sold in Adani Enterprises' },
    { date: 'Jan 21', color: '#3CB371', badge: 'SIGNAL', title: 'TRIPLE THREAT at 78%' },
    { date: 'Jan 25', color: '#E24B4A', badge: 'CRASH', title: 'Hindenburg. ₹11.5L Cr wiped.' },
  ];

  return (
    <div style={{ padding: '12px', animation: 'slideUpFade 0.6s ease-out forwards' }}>
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: '5px',
        padding: '2px 8px', marginBottom: '12px',
        background: 'rgba(59,179,113,0.06)', border: '1px solid rgba(59,179,113,0.15)',
        fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
        color: '#3CB371', letterSpacing: '0.06em',
      }}>
        <span style={{
          width: '4px', height: '4px', borderRadius: '50%', background: '#3CB371',
          animation: 'pulse 1.5s infinite',
        }} />
        Pipeline running
      </div>

      {events.map((evt, i) => (
        <div key={i} style={{
          display: 'flex', gap: '8px', marginBottom: '8px',
          paddingLeft: '8px', borderLeft: `2px solid ${evt.color}`,
        }}>
          <div>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
              color: 'rgba(240,238,232,0.15)', marginRight: '4px',
            }}>{evt.date}</span>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: '7px',
              color: evt.color, fontWeight: '500',
            }}>{evt.badge}</span>
            <div style={{
              fontSize: '11px', color: 'rgba(240,238,232,0.6)', marginTop: '1px',
              fontFamily: "'DM Sans', sans-serif", fontWeight: '400',
            }}>{evt.title}</div>
          </div>
        </div>
      ))}

      <div style={{
        fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
        color: 'rgba(240,238,232,0.1)', fontStyle: 'italic', marginTop: '8px',
      }}>
        Illustrative. Adani Jan 2023.
      </div>
    </div>
  );
}
