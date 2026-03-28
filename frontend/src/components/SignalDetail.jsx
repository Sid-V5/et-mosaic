import { useState } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

export default function SignalDetail({ selectedSignal }) {
  const [actionLoading, setActionLoading] = useState('');
  const [actionDone, setActionDone] = useState({});

  if (!selectedSignal) {
    return (
      <div style={{
        height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '32px', textAlign: 'center', color: 'var(--text-muted)',
        background: 'var(--glass-light)', borderLeft: '1px solid var(--border-subtle)'
      }}>
        <div style={{ animation: 'slideUpFade 0.6s ease-out forwards' }}>
          <div style={{
            fontSize: '48px', marginBottom: '16px', opacity: 0.8,
            animation: 'pulseSubtle 3s infinite ease-in-out'
          }}>🔍</div>
          <div style={{ fontSize: '18px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '8px' }}>Evidence Layers</div>
          <div style={{ fontSize: '13px', maxWidth: '280px', lineHeight: '1.6' }}>
            Select a signal from the feed to view its underlying evidence layers, technical confirmation, and historical accuracy.
          </div>
        </div>
      </div>
    );
  }

  const handleAction = async (actionType) => {
    setActionLoading(actionType);
    try {
      // Save to localStorage for persistence
      const existing = JSON.parse(localStorage.getItem('et_actions') || '[]');
      existing.push({
        signal_id: selectedSignal.id,
        action_type: actionType,
        headline: selectedSignal.headline,
        timestamp: new Date().toISOString(),
      });
      localStorage.setItem('et_actions', JSON.stringify(existing));

      // Also try backend (may not be implemented)
      await axios.post(`${API_BASE}/api/action`, {
        signal_id: selectedSignal.id,
        action_type: actionType,
      }).catch(() => {}); // Ignore if backend doesn't have this endpoint

      setActionDone(prev => ({ ...prev, [actionType]: true }));
      setTimeout(() => setActionDone(prev => ({ ...prev, [actionType]: false })), 3000);
    } catch (e) {
      console.error('Action error:', e);
    }
    setActionLoading('');
  };

  const s = selectedSignal;
  const tech = s.technical || {};
  const hasTickers = s.nse_tickers && s.nse_tickers.length > 0 && s.nse_tickers[0] !== '';
  const hasTechData = tech.rsi || tech.macd_class || tech.bb_signal;
  const isMacroSignal = !hasTickers;
  const actionRec = s.action_recommendation || {};

  return (
    <div style={{ padding: '16px', overflowY: 'auto', height: '100%' }}>
      {/* Header */}
      <h3 style={{ color: '#E2E8F0', fontSize: '16px', fontWeight: '700', marginBottom: '4px' }}>
        {s.headline}
      </h3>

      {/* Signal meta */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: '12px', flexWrap: 'wrap' }}>
        {s.sector && s.sector !== 'Other' && (
          <span style={{
            fontSize: '9px', fontWeight: '600', padding: '2px 8px', borderRadius: '4px',
            background: 'rgba(79, 134, 198, 0.15)', color: '#4F86C6',
          }}>
            {s.sector}
          </span>
        )}
        {(s.event_types || []).slice(0, 3).map((evt, i) => (
          <span key={i} style={{
            fontSize: '9px', fontWeight: '600', padding: '2px 8px', borderRadius: '4px',
            background: 'rgba(148, 163, 184, 0.1)', color: '#94A3B8',
          }}>
            {evt}
          </span>
        ))}
      </div>

      {/* What to watch */}
      {s.what_to_watch && (
        <div style={{
          marginBottom: '14px', padding: '8px 12px', borderRadius: '6px',
          background: 'rgba(239, 159, 39, 0.08)', border: '1px solid rgba(239, 159, 39, 0.2)',
        }}>
          <div style={{ fontSize: '9px', color: '#EF9F27', fontWeight: '700', textTransform: 'uppercase', marginBottom: '2px' }}>👁 What to Watch</div>
          <div style={{ fontSize: '12px', color: '#E2E8F0' }}>{s.what_to_watch}</div>
        </div>
      )}

      {/* 1. ET Articles — with links */}
      <Section title="ET Articles" icon="📰">
        {(s.sources || []).map((src, i) => (
          <div key={i} style={{
            padding: '8px 12px', marginBottom: '6px', borderRadius: '6px',
            background: 'rgba(79, 134, 198, 0.1)', border: '1px solid rgba(79, 134, 198, 0.2)',
          }}>
            <div style={{ color: '#E2E8F0', fontSize: '12px', fontWeight: '600' }}>{src.title || 'Article'}</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '3px' }}>
              <span style={{ color: '#64748B', fontSize: '10px' }}>{src.source}</span>
              {src.url ? (
                <a href={src.url} target="_blank" rel="noreferrer"
                  style={{ color: '#4F86C6', fontSize: '10px', textDecoration: 'none', fontWeight: '600' }}>
                  Read Article →
                </a>
              ) : (
                <span style={{ color: '#475569', fontSize: '9px', fontStyle: 'italic' }}>
                  via RSS feed
                </span>
              )}
            </div>
          </div>
        ))}
        {(!s.sources || s.sources.length === 0) && (
          <div style={{ color: '#64748B', fontSize: '12px' }}>No source articles available.</div>
        )}
      </Section>

      {/* 2. Connection Evidence — the actual scoring data */}
      <Section title="Connection Evidence" icon="🔗">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
          <MiniStat label="Similarity" value={s.similarity ? `${Math.round(s.similarity * 100)}%` : (s.market_data_confirmation ? `${Math.round(s.market_data_confirmation * 100)}%` : '—')} />
          <MiniStat label="Sentiment Δ" value={s.sentiment_velocity ? s.sentiment_velocity.toFixed(2) : '—'} />
          <MiniStat label="Accuracy" value={s.historical_match ? `${Math.round(s.historical_match * 100)}%` : '—'} />
        </div>
      </Section>

      {/* 3. Market Data */}
      <Section title="Market Data" icon="📊">
        {isMacroSignal ? (
          <div style={{
            padding: '8px 12px', borderRadius: '6px',
            background: 'rgba(148, 163, 184, 0.05)', border: '1px solid rgba(148, 163, 184, 0.1)',
          }}>
            <div style={{ fontSize: '11px', color: '#94A3B8', lineHeight: '1.5' }}>
              📌 <strong>Macro/Thematic Signal</strong> — Covers broad macro themes. Market confirmation from cross-article correlation.
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginTop: '6px' }}>
              <DataPoint label="Cross-Source" value={`${Math.round((s.similarity || s.market_data_confirmation || 0) * 100)}%`} />
              <DataPoint label="Confidence" value={`${s.confidence}%`} highlight={s.confidence >= 70} />
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <DataPoint label="Bulk Deals" value={s.bulk_deals?.length > 0 ? `${s.bulk_deals.length} found` : 'None'} />
            <DataPoint label="Volume Spike" value={s.price_data?.volume_spike ? '⚠️ Yes' : 'Normal'} />
            <DataPoint label="Price (7d)" value={s.price_data?.price_change_7d_pct ? `${s.price_data.price_change_7d_pct}%` : '—'}
              highlight={s.price_data?.price_change_7d_pct < -5} />
            <DataPoint label="Current Price" value={s.price_data?.current_price ? `₹${s.price_data.current_price}` : '—'} />
          </div>
        )}
      </Section>

      {/* 4. Technical Indicators */}
      <Section title="Technical Indicators" icon="📈">
        {isMacroSignal ? (
          <div style={{
            padding: '8px 12px', borderRadius: '6px',
            background: 'rgba(148, 163, 184, 0.05)', border: '1px solid rgba(148, 163, 184, 0.1)',
            fontSize: '11px', color: '#94A3B8',
          }}>
            📌 TA available for NSE equities only. Macro signals use cross-article sentiment analysis.
          </div>
        ) : hasTechData ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
            <DataPoint label="RSI" value={tech.rsi ? `${tech.rsi} (${tech.rsi_signal})` : '—'}
              highlight={tech.rsi_signal === 'OVERBOUGHT'} />
            <DataPoint label="MACD" value={tech.macd_class || '—'}
              highlight={tech.macd_class === 'BEARISH_CROSS'} />
            <DataPoint label="Bollinger" value={tech.bb_signal || '—'} />
            <DataPoint label="200-DMA" value={tech.dma_signal || '—'}
              highlight={tech.dma_signal === 'BELOW_200DMA'} />
          </div>
        ) : (
          <div style={{
            padding: '8px 12px', borderRadius: '6px',
            background: 'rgba(148, 163, 184, 0.05)', border: '1px solid rgba(148, 163, 184, 0.1)',
            fontSize: '11px', color: '#94A3B8',
          }}>
            Awaiting market data. TA populates during NSE trading hours.
          </div>
        )}
      </Section>

      {/* 5. Contagion */}
      <Section title="Contagion Analysis" icon="🌐">
        <DataPoint label="Type" value={s.contagion_type || 'isolated'}
          highlight={s.contagion_type === 'systemic' || s.contagion_type === 'spreading'} />
        {s.affected_peers?.length > 0 && (
          <div style={{ marginTop: '6px' }}>
            <span style={{ fontSize: '10px', color: '#64748B' }}>Affected Peers: </span>
            {s.affected_peers.map((p, i) => (
              <span key={i} style={{
                fontSize: '10px', color: '#E24B4A', marginRight: '6px', fontWeight: '600',
              }}>{p}</span>
            ))}
          </div>
        )}
        <div style={{ marginTop: '4px', color: '#94A3B8', fontSize: '11px', fontStyle: 'italic' }}>
          {s.contagion_note && s.contagion_note !== 'Signal isolated to Unknown.'
            ? s.contagion_note
            : (isMacroSignal ? 'Macro signal — tracks cross-sector sentiment spread.' : 'No peer contagion detected.')
          }
        </div>
      </Section>

      {/* AI Recommended Action */}
      {actionRec.type && (
        <div style={{
          marginBottom: '12px', padding: '10px', borderRadius: '6px',
          background: actionRec.type === 'REDUCE_EXPOSURE'
            ? 'rgba(226, 75, 74, 0.08)' : actionRec.type === 'ADD_WATCHLIST'
            ? 'rgba(59, 179, 113, 0.08)' : 'rgba(239, 159, 39, 0.08)',
          border: `1px solid ${actionRec.type === 'REDUCE_EXPOSURE'
            ? 'rgba(226, 75, 74, 0.2)' : actionRec.type === 'ADD_WATCHLIST'
            ? 'rgba(59, 179, 113, 0.2)' : 'rgba(239, 159, 39, 0.2)'}`,
        }}>
          <div style={{ fontSize: '9px', fontWeight: '700', textTransform: 'uppercase', color: '#94A3B8', marginBottom: '3px' }}>
            🤖 AI Recommendation
          </div>
          <div style={{ fontSize: '11px', color: '#E2E8F0', fontWeight: '600', marginBottom: '2px' }}>
            {actionRec.type.replace(/_/g, ' ')}
          </div>
          <div style={{ fontSize: '10px', color: '#94A3B8', lineHeight: '1.4' }}>
            {actionRec.reasoning}
          </div>
        </div>
      )}

      {/* Action Buttons — functional with feedback */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
        {['ADD_WATCHLIST', 'REDUCE_EXPOSURE', 'INCREASE_MONITORING'].map(action => (
          <button
            key={action}
            onClick={() => handleAction(action)}
            disabled={actionLoading === action}
            style={{
              flex: 1, padding: '8px 10px', borderRadius: '6px', border: 'none',
              cursor: 'pointer', fontSize: '9px', fontWeight: '800', textTransform: 'uppercase',
              letterSpacing: '0.5px', transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
              background: actionDone[action]
                ? 'rgba(59, 179, 113, 0.9)'
                : action === 'REDUCE_EXPOSURE' ? 'rgba(226, 75, 74, 0.2)'
                : action === 'ADD_WATCHLIST' ? 'rgba(59, 179, 113, 0.2)' : 'rgba(239, 159, 39, 0.2)',
              color: actionDone[action]
                ? '#FFFFFF'
                : action === 'REDUCE_EXPOSURE' ? '#E24B4A'
                : action === 'ADD_WATCHLIST' ? '#3CB371' : '#EF9F27',
              boxShadow: actionDone[action] ? '0 0 12px rgba(59, 179, 113, 0.4)' : 'none',
              transform: actionLoading === action ? 'scale(0.98)' : 'scale(1)',
            }}
          >
            {actionLoading === action ? 'SYNCING...' : actionDone[action] ? '✓ ACTION SAVED' : action.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {/* Hindi Audio */}
      {s.audio_path && (
        <div style={{ marginTop: '8px' }}>
          <div style={{ fontSize: '11px', color: '#64748B', marginBottom: '4px' }}>🎧 Audio Brief (Hinglish)</div>
          <audio controls style={{ width: '100%', height: '32px' }}
            src={`${API_BASE}/api/signal/${s.id}/audio`} />
        </div>
      )}

      {/* Disclaimer */}
      <div style={{
        marginTop: '12px', padding: '8px', borderRadius: '6px',
        background: 'rgba(148, 163, 184, 0.05)', border: '1px solid rgba(148, 163, 184, 0.1)',
        color: '#475569', fontSize: '10px', lineHeight: '1.5',
      }}>
        {s.disclaimer || 'This is for research only. Not investment advice.'}
      </div>
    </div>
  );
}

function Section({ title, icon, children }) {
  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{
        fontSize: '11px', fontWeight: '700', color: '#94A3B8', marginBottom: '6px',
        textTransform: 'uppercase', letterSpacing: '0.5px',
      }}>
        {icon} {title}
      </div>
      {children}
    </div>
  );
}

function DataPoint({ label, value, highlight = false }) {
  return (
    <div style={{
      padding: '5px 8px', borderRadius: '5px',
      background: highlight ? 'rgba(226, 75, 74, 0.1)' : 'rgba(148, 163, 184, 0.05)',
      border: highlight ? '1px solid rgba(226, 75, 74, 0.3)' : '1px solid rgba(148, 163, 184, 0.1)',
    }}>
      <div style={{ fontSize: '8px', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.3px' }}>{label}</div>
      <div style={{ fontSize: '11px', color: highlight ? '#E24B4A' : '#E2E8F0', fontWeight: '600', marginTop: '1px' }}>{value}</div>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div style={{
      padding: '5px 6px', borderRadius: '5px', textAlign: 'center',
      background: 'rgba(79, 134, 198, 0.08)', border: '1px solid rgba(79, 134, 198, 0.15)',
    }}>
      <div style={{ fontSize: '8px', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.3px' }}>{label}</div>
      <div style={{ fontSize: '12px', color: '#4F86C6', fontWeight: '700', marginTop: '1px' }}>{value}</div>
    </div>
  );
}
