import { useState, useRef, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

export default function MosaicTerminal({ selectedSignal, isOpen, onToggle, portfolio = [] }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [terminalHeight, setTerminalHeight] = useState(280);
  const [isDragging, setIsDragging] = useState(false);
  const messagesRef = useRef(null);
  const audioRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  // Resize drag
  const handleDragStart = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;
    const startY = { current: 0 };
    const handleMove = (e) => {
      setTerminalHeight(prev => {
        const delta = -e.movementY;
        return Math.max(180, Math.min(500, prev + delta));
      });
    };
    const handleUp = () => setIsDragging(false);
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
    return () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
    };
  }, [isDragging]);

  const handleSubmit = async (e) => {
    e?.preventDefault();
    const query = input.trim();
    if (!query || isTyping) return;

    setMessages(prev => [...prev, { role: 'user', text: query }]);
    setInput('');
    setIsTyping(true);

    try {
      const res = await axios.post(`${API_BASE}/api/chat`, {
        query,
        signal_id: selectedSignal?.id || null,
        portfolio: portfolio || [],
      });
      const { text, audio_path } = res.data;
      setMessages(prev => [...prev, { role: 'ai', text, audio_path }]);

      // Auto-play voice response
      if (audio_path && audioRef.current) {
        audioRef.current.src = `${API_BASE}/api/chat/audio/${audio_path}`;
        audioRef.current.play().catch(() => {});
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'ai',
        text: 'Connection error. Backend may be offline.',
        audio_path: '',
      }]);
    }
    setIsTyping(false);
  };

  // Suggestion chips
  const suggestions = [
    'Strongest convergence right now?',
    'Which sectors have high-severity edges?',
    'Risk summary for my portfolio',
  ];

  return (
    <div style={{
      borderTop: '1px solid rgba(240,165,0,0.15)',
      flexShrink: 0,
      background: '#080E14',
      width: '100%',
    }}>
      {/* Header / toggle */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 14px', cursor: 'pointer',
          background: 'rgba(240,165,0,0.03)',
          borderBottom: isOpen ? '1px solid rgba(255,255,255,0.05)' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: '13px',
            color: '#F0A500', letterSpacing: '0.1em', fontWeight: '500',
          }}>
            ◈ MOSAIC TERMINAL
          </span>
          {messages.length > 0 && !isOpen && (
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px',
              color: 'rgba(240,238,232,0.15)',
            }}>
              {messages.length} messages
            </span>
          )}
        </div>
        <span style={{
          color: 'rgba(240,238,232,0.2)', fontSize: '12px',
          transform: isOpen ? 'rotate(180deg)' : 'rotate(0)',
          transition: 'transform 0.2s ease',
        }}>▼</span>
      </div>

      {/* Terminal body */}
      {isOpen && (
        <div style={{ height: `${terminalHeight}px`, display: 'flex', flexDirection: 'column' }}>
          {/* Resize handle */}
          <div
            onMouseDown={handleDragStart}
            style={{
              height: '4px', cursor: 'ns-resize',
              background: isDragging ? 'rgba(240,165,0,0.15)' : 'transparent',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.target.style.background = 'rgba(240,165,0,0.1)'}
            onMouseLeave={e => { if (!isDragging) e.target.style.background = 'transparent'; }}
          />

          {/* Messages */}
          <div
            ref={messagesRef}
            style={{
              flex: 1, overflowY: 'auto', padding: '8px 14px',
            }}
          >
            {messages.length === 0 && (
              <div style={{ padding: '8px 0' }}>
                <div style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px',
                  color: 'rgba(240,238,232,0.12)', marginBottom: '10px',
                }}>
                  Ask about connections, signals, risks, or convergence patterns.
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {suggestions.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => { setInput(s); }}
                      style={{
                        background: 'rgba(240,165,0,0.04)',
                        border: '1px solid rgba(240,165,0,0.1)',
                        padding: '4px 10px', cursor: 'pointer',
                        fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px',
                        color: 'rgba(240,238,232,0.3)', borderRadius: 0,
                      }}
                    >{s}</button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} style={{
                marginBottom: '12px',
                textAlign: msg.role === 'user' ? 'right' : 'left',
              }}>
                <div style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: msg.role === 'user' ? '13px' : '14px',
                  color: msg.role === 'user' ? 'rgba(240,238,232,0.35)' : 'rgba(240,238,232,0.7)',
                  lineHeight: '1.5',
                  display: 'inline-block',
                  maxWidth: '90%',
                  textAlign: 'left',
                  padding: msg.role === 'ai' ? '6px 8px' : '0',
                  background: msg.role === 'ai' ? 'rgba(255,255,255,0.015)' : 'transparent',
                  border: msg.role === 'ai' ? '1px solid rgba(255,255,255,0.03)' : 'none',
                }}>
                  <span style={{ color: '#F0A500', marginRight: '4px' }}>
                    {msg.role === 'user' ? '>' : '◈'}
                  </span>
                  {msg.text}
                </div>
                {msg.audio_path && (
                  <div style={{ marginTop: '4px' }}>
                    <button
                      onClick={() => {
                        if (audioRef.current) {
                          audioRef.current.src = `${API_BASE}/api/chat/audio/${msg.audio_path}`;
                          audioRef.current.play().catch(() => {});
                        }
                      }}
                      style={{
                        background: 'rgba(240,165,0,0.06)',
                        border: '1px solid rgba(240,165,0,0.15)',
                        padding: '4px 10px', cursor: 'pointer',
                        fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px',
                        color: '#F0A500', borderRadius: 0,
                      }}
                    >▶ PLAY VOICE</button>
                  </div>
                )}
              </div>
            ))}

            {isTyping && (
              <div style={{
                fontFamily: "'IBM Plex Mono', monospace", fontSize: '13px',
                color: 'rgba(240,165,0,0.4)',
                animation: 'blink 1s infinite',
              }}>
                <span style={{ color: '#F0A500', marginRight: '4px' }}>◈</span>
                thinking...
              </div>
            )}
          </div>

          {/* Input */}
          <form onSubmit={handleSubmit} style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '6px 14px',
            borderTop: '1px solid rgba(255,255,255,0.05)',
            flexShrink: 0,
          }}>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: '13px',
              color: '#F0A500',
            }}>{'>'}</span>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Ask about connections, signals, risks..."
              disabled={isTyping}
              style={{
                flex: 1, background: 'transparent', border: 'none',
                borderBottom: '1px solid rgba(240,165,0,0.15)',
                padding: '6px 0', color: 'rgba(240,238,232,0.9)',
                fontSize: '14px', fontFamily: "'IBM Plex Mono', monospace",
                outline: 'none',
              }}
            />
            <button
              type="submit"
              disabled={isTyping || !input.trim()}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                fontFamily: "'IBM Plex Mono', monospace", fontSize: '16px',
                color: input.trim() ? '#F0A500' : 'rgba(240,238,232,0.1)',
                padding: '0 8px',
              }}
            >↵</button>
          </form>
        </div>
      )}

      {/* Hidden audio element */}
      <audio ref={audioRef} style={{ display: 'none' }} />

      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
