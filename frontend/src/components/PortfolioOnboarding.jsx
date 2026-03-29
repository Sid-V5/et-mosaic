import { useState, useEffect } from 'react';

export default function PortfolioOnboarding({ onClose, existingPortfolio = [], existingUsername = '' }) {
  const [username, setUsername] = useState(existingUsername);
  const [tickers, setTickers] = useState(() => {
    const base = existingPortfolio.length > 0 ? [...existingPortfolio] : [];
    while (base.length < 10) base.push('');
    return base.slice(0, 10);
  });

  const placeholders = ['HDFCBANK', 'TCS', 'RELIANCE', 'INFY', 'ICICIBANK', 'SBIN', 'VEDL', 'TATASTEEL', 'ITC', 'WIPRO'];

  const handleChange = (index, value) => {
    const updated = [...tickers];
    updated[index] = value.toUpperCase().trim();
    setTickers(updated);
  };

  const handleSave = () => {
    const valid = tickers.filter(t => t.length > 0);
    const name = username.trim() || 'default';
    onClose(valid, name);
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(2,5,8,0.9)', backdropFilter: 'blur(16px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: '#080E14',
        padding: '32px', width: '400px',
        border: '1px solid rgba(255,255,255,0.07)',
      }}>
        <div style={{
          fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
          color: '#F0A500', letterSpacing: '0.12em', marginBottom: '4px',
        }}>ET MOSAIC</div>
        <h2 style={{
          color: '#F0EEE8', fontSize: '18px', fontWeight: '500',
          fontFamily: "'DM Sans', sans-serif", marginBottom: '4px',
        }}>
          {existingUsername ? 'Edit Portfolio' : 'Setup'}
        </h2>
        <p style={{
          color: 'rgba(240,238,232,0.3)', fontSize: '11px', marginBottom: '16px',
          fontFamily: "'DM Sans', sans-serif",
        }}>
          Enter your name and NSE tickers to personalise signals.
        </p>

        {/* Username */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
            color: 'rgba(240,238,232,0.2)', letterSpacing: '0.08em', marginBottom: '4px',
          }}>NAME</div>
          <input
            value={username}
            onChange={e => setUsername(e.target.value)}
            placeholder="Your name"
            style={{
              width: '100%', background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.07)',
              padding: '8px 10px', color: '#F0EEE8',
              fontSize: '12px', fontFamily: "'DM Sans', sans-serif",
              outline: 'none', boxSizing: 'border-box',
            }}
            onFocus={e => e.target.style.borderColor = 'rgba(240,165,0,0.3)'}
            onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.07)'}
          />
        </div>

        {/* Tickers */}
        <div style={{
          fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
          color: 'rgba(240,238,232,0.2)', letterSpacing: '0.08em', marginBottom: '6px',
        }}>NSE TICKERS</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
          {tickers.map((ticker, i) => (
            <input
              key={i}
              value={ticker}
              onChange={e => handleChange(i, e.target.value)}
              placeholder={placeholders[i] || ''}
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
                padding: '7px 8px', color: '#F0EEE8',
                fontSize: '11px', fontWeight: '500', letterSpacing: '0.5px',
                fontFamily: "'IBM Plex Mono', monospace",
                outline: 'none',
              }}
              onFocus={e => e.target.style.borderColor = 'rgba(240,165,0,0.3)'}
              onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.07)'}
            />
          ))}
        </div>

        <button
          onClick={handleSave}
          style={{
            width: '100%', marginTop: '16px', padding: '10px',
            background: '#F0A500', border: 'none',
            color: '#020508', fontSize: '11px', fontWeight: '600',
            fontFamily: "'IBM Plex Mono', monospace",
            cursor: 'pointer', letterSpacing: '0.06em',
          }}
        >
          {existingUsername ? 'UPDATE' : 'START MONITORING'}
        </button>

        <button
          onClick={() => onClose(existingPortfolio, existingUsername || 'default')}
          style={{
            width: '100%', marginTop: '6px', padding: '8px',
            background: 'transparent', border: '1px solid rgba(255,255,255,0.05)',
            color: 'rgba(240,238,232,0.2)', fontSize: '10px',
            fontFamily: "'IBM Plex Mono', monospace",
            cursor: 'pointer',
          }}
        >
          {existingUsername ? 'Cancel' : 'Skip'}
        </button>
      </div>
    </div>
  );
}
