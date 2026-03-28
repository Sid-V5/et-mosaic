import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

const SEVERITY_STYLES = {
  high: { bg: 'rgba(239, 68, 68, 0.15)', color: '#EF4444', border: 'rgba(239, 68, 68, 0.3)' },
  medium: { bg: 'rgba(245, 158, 11, 0.15)', color: '#F59E0B', border: 'rgba(245, 158, 11, 0.3)' },
  low: { bg: 'rgba(16, 185, 129, 0.15)', color: '#10B981', border: 'rgba(16, 185, 129, 0.3)' },
};

function formatTimeAgo(isoTimestamp) {
  if (!isoTimestamp) return 'Building...';
  const diff = Math.floor((Date.now() - new Date(isoTimestamp).getTime()) / 1000);
  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function SignalFeed({ signals = [], onSignalClick, selectedSignalId }) {
  const [mounted, setMounted] = useState(false);
  const [pipelineInfo, setPipelineInfo] = useState(null);
  const [, setTick] = useState(0); // force re-render for relative time

  useEffect(() => { setMounted(true); }, []);

  // Fetch pipeline status for real timing
  useEffect(() => {
    const fetchPipelineStatus = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/pipeline/status`);
        setPipelineInfo(res.data);
      } catch { /* ignore */ }
    };
    fetchPipelineStatus();
    const interval = setInterval(fetchPipelineStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Update relative time every 30s
  useEffect(() => {
    const interval = setInterval(() => setTick(t => t + 1), 30000);
    return () => clearInterval(interval);
  }, []);

  const directCount = signals.filter(s => s.portfolio_relevance === 'direct').length;
  const lastRunTime = pipelineInfo?.started_at || pipelineInfo?.last_run;
  const lastRunDisplay = lastRunTime ? formatTimeAgo(lastRunTime) : (signals.length > 0 ? 'Active' : 'Building...');

  // Calculate next run (pipeline runs every 15 min)
  const getNextRun = () => {
    if (!lastRunTime) return '';
    const lastMs = new Date(lastRunTime).getTime();
    const nextMs = lastMs + 15 * 60 * 1000;
    const diffSec = Math.max(0, Math.floor((nextMs - Date.now()) / 1000));
    if (diffSec <= 0) return 'Imminent';
    if (diffSec < 60) return `${diffSec}s`;
    return `${Math.floor(diffSec / 60)}m`;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Stats Row */}
      <div style={{
        display: 'flex', gap: '16px', padding: '16px',
        borderBottom: '1px solid var(--border-medium)',
        background: 'var(--glass-light)',
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '28px', fontWeight: '800', color: 'var(--text-primary)' }}>{signals.length}</div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: '600' }}>Active Signals</div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '28px', fontWeight: '800', color: 'var(--accent-blue)' }}>{directCount}</div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: '600' }}>In Portfolio</div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-secondary)', marginTop: '4px' }}>
            {lastRunDisplay}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px', fontWeight: '600' }}>Last Pipeline Sync</div>
          {getNextRun() && (
            <div style={{ fontSize: '9px', color: '#475569', marginTop: '2px' }}>
              Next: {getNextRun()}
            </div>
          )}
        </div>
      </div>

      {/* Signal Cards */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {signals.length === 0 && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            height: '100%', padding: '32px', textAlign: 'center', color: 'var(--text-muted)',
            animation: 'slideUpFade 0.6s ease-out forwards'
          }}>
            <div style={{
              fontSize: '40px', marginBottom: '16px',
              animation: 'pulseSubtle 2s infinite ease-in-out'
            }}>📡</div>
            <div style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '8px' }}>No Signals Yet</div>
            <div style={{ fontSize: '13px', maxWidth: '250px', lineHeight: '1.5' }}>
              The multi-agent orchestrator is currently scanning the market. Signals will appear here once connections are found.
            </div>
          </div>
        )}
        {signals.map((signal, index) => {
          const isSelected = selectedSignalId === signal.id;
          const severity = SEVERITY_STYLES[signal.severity] || SEVERITY_STYLES.low;

          return (
            <div
              key={signal.id || index}
              onClick={() => onSignalClick?.(signal)}
              style={{
                background: isSelected ? 'rgba(59, 130, 246, 0.1)' : 'var(--bg-elevated)',
                border: isSelected ? '1px solid var(--accent-blue)' : '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '16px',
                marginBottom: '12px',
                cursor: 'pointer',
                transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                transform: mounted ? 'translateX(0)' : 'translateX(100%)',
                transitionDelay: `${index * 80}ms`,
              }}
            >
              {/* Badges */}
              <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', flexWrap: 'wrap' }}>
                <span style={{
                  fontSize: '10px', fontWeight: '700', textTransform: 'uppercase',
                  padding: '2px 8px', borderRadius: '4px', letterSpacing: '0.5px',
                  background: severity.bg, color: severity.color,
                }}>
                  {signal.severity}
                </span>
                {signal.freshness === 'BREAKING' && (
                  <span style={{
                    fontSize: '10px', fontWeight: '700', textTransform: 'uppercase',
                    padding: '2px 8px', borderRadius: '4px', letterSpacing: '0.5px',
                    background: '#FEE2E2', color: '#DC2626',
                    animation: 'pulse 1.5s ease-in-out infinite',
                  }}>
                    BREAKING
                  </span>
                )}
                {signal.portfolio_relevance === 'direct' && (
                  <span style={{
                    fontSize: '10px', fontWeight: '700', padding: '2px 8px',
                    borderRadius: '4px', background: '#DBEAFE', color: '#2563EB',
                  }}>
                    PORTFOLIO
                  </span>
                )}
                <span style={{
                  fontSize: '10px', fontWeight: '600', padding: '2px 8px', borderRadius: '4px',
                  background: 'rgba(148, 163, 184, 0.15)', color: '#94A3B8',
                }}>
                  {signal.signal_type?.replace(/_/g, ' ')}
                </span>
              </div>

              {/* Headline */}
              <div style={{ fontWeight: '700', color: '#E2E8F0', fontSize: '14px', marginBottom: '6px' }}>
                {signal.headline}
              </div>

              {/* Summary */}
              <div style={{ color: '#94A3B8', fontSize: '12px', lineHeight: '1.5', marginBottom: '8px' }}>
                {signal.summary?.slice(0, 150)}{signal.summary?.length > 150 ? '...' : ''}
              </div>

              {/* Confidence Bar */}
              <div style={{ marginBottom: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
                  <span style={{ fontSize: '10px', color: '#64748B' }}>Confidence</span>
                  <span style={{ fontSize: '10px', color: '#94A3B8', fontWeight: '600' }}>{signal.confidence}%</span>
                </div>
                <div style={{ height: '4px', background: 'rgba(148, 163, 184, 0.15)', borderRadius: '2px' }}>
                  <div style={{
                    height: '100%', borderRadius: '2px',
                    width: `${signal.confidence}%`,
                    background: signal.confidence > 70 ? '#E24B4A' : signal.confidence > 50 ? '#EF9F27' : '#3CB371',
                    transition: 'width 0.5s ease',
                  }} />
                </div>
              </div>

              {/* Sources */}
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {(signal.sources || []).slice(0, 3).map((src, i) => (
                  <span key={i} style={{
                    fontSize: '9px', color: '#64748B', padding: '1px 6px',
                    borderRadius: '3px', background: 'rgba(148, 163, 184, 0.1)',
                  }}>
                    {src.source || src.title?.slice(0, 30)}
                  </span>
                ))}
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
