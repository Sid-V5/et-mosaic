import { useState, useEffect } from 'react';

export default function PortfolioOnboarding({ onClose }) {
  const [tickers, setTickers] = useState(Array(10).fill(''));

  const handleChange = (index, value) => {
    const updated = [...tickers];
    updated[index] = value.toUpperCase().trim();
    setTickers(updated);
  };

  const handleSave = () => {
    const valid = tickers.filter(t => t.length > 0);
    localStorage.setItem('et_portfolio', JSON.stringify(valid));
    onClose(valid);
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0, 0, 0, 0.8)', backdropFilter: 'blur(10px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: 'linear-gradient(135deg, #0F172A, #1E293B)',
        borderRadius: '16px', padding: '32px', width: '420px',
        border: '1px solid rgba(148, 163, 184, 0.15)',
        boxShadow: '0 25px 50px rgba(0, 0, 0, 0.5)',
      }}>
        <h2 style={{ color: '#E2E8F0', fontSize: '22px', fontWeight: '800', marginBottom: '4px' }}>
          Your Portfolio
        </h2>
        <p style={{ color: '#94A3B8', fontSize: '13px', marginBottom: '20px' }}>
          Enter your NSE ticker symbols to personalise signals.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          {tickers.map((ticker, i) => (
            <input
              key={i}
              value={ticker}
              onChange={e => handleChange(i, e.target.value)}
              placeholder={['HDFCBANK', 'TCS', 'RELIANCE', 'INFY', 'ICICIBANK', 'SBIN', 'VEDL', 'TATASTEEL', 'ITC', 'WIPRO'][i] || 'TICKER'}
              style={{
                background: 'rgba(30, 41, 59, 0.8)', border: '1px solid rgba(148, 163, 184, 0.2)',
                borderRadius: '8px', padding: '10px 12px', color: '#E2E8F0',
                fontSize: '13px', fontWeight: '600', letterSpacing: '0.5px',
                outline: 'none', transition: 'border-color 0.2s',
              }}
              onFocus={e => e.target.style.borderColor = '#4F86C6'}
              onBlur={e => e.target.style.borderColor = 'rgba(148, 163, 184, 0.2)'}
            />
          ))}
        </div>

        <button
          onClick={handleSave}
          style={{
            width: '100%', marginTop: '20px', padding: '12px',
            background: 'linear-gradient(135deg, #4F86C6, #7B68EE)',
            border: 'none', borderRadius: '8px', color: '#FFFFFF',
            fontSize: '14px', fontWeight: '700', cursor: 'pointer',
            transition: 'opacity 0.2s',
          }}
          onMouseOver={e => e.target.style.opacity = '0.9'}
          onMouseOut={e => e.target.style.opacity = '1'}
        >
          Save & Start Monitoring
        </button>

        <button
          onClick={() => onClose([])}
          style={{
            width: '100%', marginTop: '8px', padding: '10px',
            background: 'transparent', border: '1px solid rgba(148, 163, 184, 0.2)',
            borderRadius: '8px', color: '#64748B', fontSize: '12px',
            cursor: 'pointer',
          }}
        >
          Skip for now
        </button>
      </div>
    </div>
  );
}
