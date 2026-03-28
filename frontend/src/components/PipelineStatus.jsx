import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

export default function PipelineStatus() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/pipeline/status`);
        setStatus(res.data);
      } catch (e) {
        console.error('Pipeline status error:', e);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 60000);
    return () => clearInterval(interval);
  }, []);

  const getColor = () => {
    if (!status) return '#64748B';
    switch (status.status) {
      case 'complete': return '#3CB371';
      case 'running': return '#EF9F27';
      case 'partial': return '#EF9F27';
      case 'failed': return '#E24B4A';
      default: return '#64748B';
    }
  };

  const getLabel = () => {
    if (!status) return 'Connecting...';
    if (status.status === 'running') return 'LIVE';
    if (status.status === 'complete') {
      if (status.started_at) {
        const diff = Math.round((Date.now() - new Date(status.started_at).getTime()) / 60000);
        return diff < 1 ? 'LIVE' : `${diff}m ago`;
      }
      return 'LIVE';
    }
    return status.status.toUpperCase();
  };

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '6px',
      padding: '4px 10px', borderRadius: '20px',
      background: 'rgba(30, 41, 59, 0.6)',
      border: '1px solid rgba(148, 163, 184, 0.1)',
    }}>
      <div style={{
        width: '8px', height: '8px', borderRadius: '50%',
        background: getColor(),
        animation: status?.status === 'running' || status?.status === 'complete' ?
          'statusPulse 1.5s ease-in-out infinite' : 'none',
      }} />
      <span style={{ fontSize: '11px', color: '#94A3B8', fontWeight: '600' }}>
        {getLabel()}
      </span>
      {status?.articles_ingested > 0 && (
        <span style={{ fontSize: '10px', color: '#64748B' }}>
          · {status.articles_ingested} articles
        </span>
      )}
      <style>{`
        @keyframes statusPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
