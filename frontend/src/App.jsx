import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import axios from 'axios';
import KnowledgeGraph from './components/KnowledgeGraph';
import SignalFeed from './components/SignalFeed';
import SignalDetail from './components/SignalDetail';
import PortfolioOnboarding from './components/PortfolioOnboarding';
import BacktestPanel from './components/BacktestPanel';
import MosaicTerminal from './components/MosaicTerminal';

const API_BASE = 'http://localhost:8000';

export default function App() {
  const [signals, setSignals] = useState([]);
  const [allSignalsLoaded, setAllSignalsLoaded] = useState(false);
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [portfolio, setPortfolio] = useState([]);
  const [username, setUsername] = useState('');
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showBacktest, setShowBacktest] = useState(false);
  const [showPortfolioEditor, setShowPortfolioEditor] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [minConfidence, setMinConfidence] = useState(40);
  const [pipelineInfo, setPipelineInfo] = useState(null);
  const [showGlobal, setShowGlobal] = useState(false); // India-only by default
  const [rightPanelWidth, setRightPanelWidth] = useState(500);
  const [isResizing, setIsResizing] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(false);

  // --- Resizable right panel ---
  const handleResizeStart = useCallback((e) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;
    const handleMove = (e) => {
      const newWidth = window.innerWidth - e.clientX;
      setRightPanelWidth(Math.max(400, Math.min(700, newWidth)));
    };
    const handleUp = () => setIsResizing(false);
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
    return () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
    };
  }, [isResizing]);

  // Load user + portfolio
  useEffect(() => {
    const storedUser = localStorage.getItem('et_username');
    if (storedUser) {
      setUsername(storedUser);
      const stored = localStorage.getItem(`et_portfolio_${storedUser}`);
      if (stored) {
        try { setPortfolio(JSON.parse(stored)); } catch { setPortfolio([]); }
      }
    } else {
      setShowOnboarding(true);
    }
  }, []);

  // Fetch pipeline status
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/pipeline/status`);
        setPipelineInfo(res.data);
      } catch { /* offline */ }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      const portfolioStr = portfolio.join(',');
      const params = {};
      if (portfolioStr) params.portfolio = portfolioStr;
      if (searchQuery) params.q = searchQuery;

      const [sigRes, graphRes] = await Promise.all([
        axios.get(`${API_BASE}/api/signals`, { params }).catch(() => ({ data: { signals: [] } })),
        axios.get(`${API_BASE}/api/graph`).catch(() => ({ data: { nodes: [], edges: [] } })),
      ]);

      const fetchedSignals = sigRes.data?.signals || [];
      setSignals(fetchedSignals);
      if (fetchedSignals.length > 0) setAllSignalsLoaded(true);

      // Only update graph if data actually changed (prevents D3 simulation reset)
      const newGraph = graphRes.data || { nodes: [], edges: [] };
      setGraphData(prev => {
        const prevNodeIds = (prev.nodes || []).map(n => n.id).sort().join(',');
        const newNodeIds = (newGraph.nodes || []).map(n => n.id).sort().join(',');
        const prevEdgeCount = (prev.edges || []).length;
        const newEdgeCount = (newGraph.edges || []).length;
        if (prevNodeIds === newNodeIds && prevEdgeCount === newEdgeCount) return prev;
        return newGraph;
      });
    } catch (e) {
      console.error('Data fetch error:', e);
    }
  }, [portfolio, searchQuery]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 300000); // 5 min refresh (pipeline runs every 15m)
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleOnboardingClose = (tickers, name) => {
    if (name) {
      setUsername(name);
      localStorage.setItem('et_username', name);
      localStorage.setItem(`et_portfolio_${name}`, JSON.stringify(tickers));
    }
    setPortfolio(tickers);
    setShowOnboarding(false);
  };

  const handlePortfolioSave = (tickers, name) => {
    const user = name || username;
    if (user) localStorage.setItem(`et_portfolio_${user}`, JSON.stringify(tickers));
    setPortfolio(tickers);
    setShowPortfolioEditor(false);
  };

  const handleNodeClick = (node) => {
    const matchingSignal = signals.find(s =>
      s.company_names?.some(c => node.label?.toLowerCase().includes(c.toLowerCase())) ||
      s.nse_tickers?.some(t => node.id?.includes(t.toLowerCase()))
    );
    if (matchingSignal) setSelectedSignal(matchingSignal);
  };

  // Global companies list (used for filtering signals & graph)  
  const GLOBAL_COMPANIES = new Set([
    'tesla', 'apple', 'microsoft', 'google', 'alphabet', 'amazon', 'meta',
    'nvidia', 'goldman sachs', 'jpmorgan', 'citigroup', 'berkshire',
    'spacex', 'netflix', 'amd', 'intel', 'oracle', 'salesforce', 'adobe',
    'paypal', 'uber', 'airbnb', 'coinbase', 'snap', 'spotify', 'palantir',
    'broadcom', 'qualcomm', 'texas instruments', 'taiwan semicon',
    'sk hynix', 'samsung', 'sony', 'toyota', 'softbank', 'alibaba',
    'paychex', 'harley-davidson', 'warren buffett', 'blackrock',
    'morgan stanley', 'bank of america', 'wells fargo', 'exxon',
    'chevron', 'bp ', 'shell', 'pfizer', 'moderna', 'acme solar',
    'quest diagnostics', 'polymarket', 'bitmine', 'intercontinental',
    'every ma', 'magnificen', 'us stock', 'wall street',
    'arm holdings', 'super micro', 'jefferies', 'hyundai',
    'accel', 'national stock', 'dow jones', 'nasdaq', 'apple inc',
    'meta platforms', 'meta set', 'workers everywhere',
    'global stocks', 'magnificent 7', 'in wake of us',
    'us stocks', 'spectrum shift', 'stocks to buy',
    'kill switch', 'silver lining',
  ]);

  // Filter signals by confidence AND region
  const filteredSignals = signals
    .filter(s => (s.confidence || 0) >= minConfidence)
    .filter(s => {
      if (showGlobal) return true; // Global mode: show everything
      // NSE mode: hide signals where ALL companies are global
      const companies = s.company_names || [];
      if (companies.length === 0) return true;
      const hasIndian = companies.some(c => {
        const cl = c.toLowerCase();
        for (const gc of GLOBAL_COMPANIES) {
          if (cl.includes(gc)) return false;
        }
        return true;
      });
      // Also keep if signal has NSE tickers
      const hasTickers = (s.nse_tickers || []).length > 0;
      return hasIndian || hasTickers;
    })
    // Sort: BREAKING first, then by confidence descending
    .sort((a, b) => {
      const aBreaking = a.freshness === 'BREAKING' ? 1 : 0;
      const bBreaking = b.freshness === 'BREAKING' ? 1 : 0;
      if (aBreaking !== bBreaking) return bBreaking - aBreaking;
      return (b.confidence || 0) - (a.confidence || 0);
    });

  // Filter graph for India vs Global

  const isGlobalNode = (n) => {
    if (n.type === 'sector') return false; // always keep sector hubs
    const label = (n.label || '').toLowerCase();
    const title = (n.metadata?.title || '').toLowerCase();
    const source = (n.metadata?.source || '').toLowerCase();
    // Check if label or title matches any global company
    for (const gc of GLOBAL_COMPANIES) {
      if (label.includes(gc) || title.includes(gc)) return true;
    }
    // Articles from non-ET sources without NSE tickers
    const etSources = ['et ', 'economic times', 'moneycontrol', 'nse'];
    const isEtSource = etSources.some(s => source.startsWith(s) || source.includes(s));
    const hasTickers = (n.metadata?.nse_tickers || []).length > 0;
    if (!isEtSource && !hasTickers && (n.type === 'article')) return true;
    return false;
  };

  const filteredGraphData = useMemo(() => {
    return showGlobal ? graphData : (() => {
      const kept = graphData.nodes?.filter(n => !isGlobalNode(n)) || [];
      const keptIds = new Set(kept.map(n => n.id));
      return {
        nodes: kept,
        edges: (graphData.edges || []).filter(e => keptIds.has(e.source) && keptIds.has(e.target)),
      };
    })();
  }, [showGlobal, graphData]);

  // Pipeline helpers
  const articleCount = pipelineInfo?.articles_ingested || 0;
  const pipelineStatusColor = !pipelineInfo ? '#4B5563' :
    pipelineInfo.status === 'complete' ? '#3CB371' :
    pipelineInfo.status === 'running' ? '#F0A500' :
    pipelineInfo.status === 'failed' ? '#E24B4A' : '#4B5563';
  const pipelineLabel = !pipelineInfo ? 'Offline' :
    pipelineInfo.status === 'running' ? 'LIVE' :
    pipelineInfo.status === 'complete' ? (() => {
      if (pipelineInfo.started_at) {
        const diff = Math.round((Date.now() - new Date(pipelineInfo.started_at).getTime()) / 60000);
        return diff < 1 ? 'LIVE' : `${diff}m ago`;
      }
      return 'LIVE';
    })() : pipelineInfo.status?.toUpperCase();

  return (
    <div style={{
      width: '100vw', height: '100vh', overflow: 'hidden',
      background: '#020508', color: '#F0EEE8',
      fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
      display: 'flex', flexDirection: 'column',
      userSelect: isResizing ? 'none' : 'auto',
      position: 'relative',
    }}>
      {/* Ambient Dashboard Background */}
      <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 0, pointerEvents: 'none' }}>
        <defs>
          <pattern id="gridPattern" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(14,165,160,0.03)" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#gridPattern)" />
        <circle cx="20%" cy="20%" r="20%" fill="none" stroke="rgba(240,165,0,0.02)" strokeWidth="0.5" style={{animation: 'pulse-ring-ambient 4s infinite alternate'}} />
        <circle cx="80%" cy="80%" r="30%" fill="none" stroke="rgba(14,165,160,0.02)" strokeWidth="0.5" style={{animation: 'pulse-ring-ambient 6s infinite alternate', animationDelay: '1s'}} />
      </svg>

      {/* Top Bar */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 20px', height: '44px', flexShrink: 0,
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        background: 'rgba(2,5,8,0.95)', backdropFilter: 'blur(12px)',
        zIndex: 100,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              width: '6px', height: '6px', borderRadius: '50%',
              background: '#F0A500', display: 'inline-block',
            }} />
            <h1 style={{
              fontSize: '13px', fontWeight: '500', letterSpacing: '0.12em',
              fontFamily: "'IBM Plex Mono', monospace",
              color: '#F0EEE8', margin: 0,
            }}>ET MOSAIC</h1>
          </div>
          {username && (
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px',
              color: 'rgba(240,238,232,0.15)', letterSpacing: '0.05em',
            }}>{username}</span>
          )}
          {/* India / Global toggle */}
          <div style={{
            display: 'flex', border: '1px solid rgba(255,255,255,0.07)',
          }}>
            <button onClick={() => setShowGlobal(false)} style={{
              padding: '3px 10px', border: 'none', cursor: 'pointer',
              fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
              fontWeight: '500', letterSpacing: '0.06em',
              background: !showGlobal ? 'rgba(240,165,0,0.12)' : 'transparent',
              color: !showGlobal ? '#F0A500' : 'rgba(240,238,232,0.2)',
            }}>NSE</button>
            <button onClick={() => setShowGlobal(true)} style={{
              padding: '3px 10px', border: 'none', cursor: 'pointer',
              borderLeft: '1px solid rgba(255,255,255,0.07)',
              fontFamily: "'IBM Plex Mono', monospace", fontSize: '9px',
              fontWeight: '500', letterSpacing: '0.06em',
              background: showGlobal ? 'rgba(240,165,0,0.12)' : 'transparent',
              color: showGlobal ? '#F0A500' : 'rgba(240,238,232,0.2)',
            }}>GLOBAL</button>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search..."
            style={{
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)',
              padding: '4px 10px', color: '#F0EEE8',
              fontSize: '11px', width: '140px', outline: 'none',
              fontFamily: "'IBM Plex Mono', monospace", borderRadius: 0,
            }}
          />
          <button
            onClick={() => setShowPortfolioEditor(true)}
            title="Edit portfolio"
            style={{
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)',
              padding: '4px 8px', color: 'rgba(240,238,232,0.4)',
              cursor: 'pointer', fontSize: '11px', borderRadius: 0,
            }}
          >⚙</button>
          <button
            onClick={() => setShowBacktest(true)}
            style={{
              background: 'rgba(240,165,0,0.08)',
              border: '1px solid rgba(240,165,0,0.2)',
              padding: '4px 12px', color: '#F0A500',
              cursor: 'pointer', fontSize: '9px', fontWeight: '500',
              fontFamily: "'IBM Plex Mono', monospace",
              letterSpacing: '0.08em', borderRadius: 0,
            }}
          >CASE STUDY: ADANI 2023</button>
        </div>
      </header>      {/* Main Content Area — column layout: panels above, terminal below */}
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden', position: 'relative', zIndex: 1 }}>
        {/* Top row: 3-panel layout */}
        <main style={{
          display: 'flex', flex: 1, overflow: 'hidden',
        }}>
          {/* Left Panel: Evidence Layers / Signal Feed */}
          <div style={{
            width: '320px', flexShrink: 0,
            background: '#050A10', borderRight: '1px solid rgba(255,255,255,0.07)',
            display: 'flex', flexDirection: 'column', overflow: 'hidden'
          }}>
            {/* Stats bar */}
            <div style={{
              display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.07)',
              flexShrink: 0,
            }}>
              <div style={{ flex: 1, padding: '10px 14px', borderRight: '1px solid rgba(255,255,255,0.07)' }}>
                <div style={{
                  fontSize: '24px', fontWeight: '500', color: '#F0EEE8',
                  fontFamily: "'IBM Plex Mono', monospace",
                }}>{filteredSignals.length}</div>
                <div style={{
                  fontSize: '8px', color: 'rgba(240,238,232,0.25)', textTransform: 'uppercase',
                  letterSpacing: '0.1em', fontFamily: "'IBM Plex Mono', monospace",
                }}>SIGNALS</div>
              </div>
              <div style={{ flex: 1, padding: '10px 14px', borderRight: '1px solid rgba(255,255,255,0.07)' }}>
                <div style={{
                  fontSize: '24px', fontWeight: '500',
                  color: portfolio.length > 0 ? '#F0A500' : 'rgba(240,238,232,0.15)',
                  fontFamily: "'IBM Plex Mono', monospace",
                }}>{filteredSignals.filter(s => s.portfolio_relevance === 'direct').length}</div>
                {portfolio.length === 0 ? (
                  <div onClick={() => setShowPortfolioEditor(true)} style={{
                    fontSize: '8px', color: '#F0A500', cursor: 'pointer',
                    fontFamily: "'IBM Plex Mono', monospace", letterSpacing: '0.05em',
                  }}>Set portfolio &rarr;</div>
                ) : (
                  <div style={{
                    fontSize: '8px', color: 'rgba(240,238,232,0.25)', textTransform: 'uppercase',
                    letterSpacing: '0.1em', fontFamily: "'IBM Plex Mono', monospace",
                  }}>IN PORTFOLIO</div>
                )}
              </div>
              <div style={{ flex: 1, padding: '10px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{
                    width: '6px', height: '6px', borderRadius: '50%',
                    background: pipelineStatusColor,
                    animation: pipelineInfo?.status === 'running' || pipelineInfo?.status === 'complete'
                      ? 'statusPulse 1.5s ease-in-out infinite' : 'none',
                    display: 'inline-block',
                  }} />
                  <span style={{
                    fontSize: '13px', fontWeight: '500', color: 'rgba(240,238,232,0.5)',
                    fontFamily: "'IBM Plex Mono', monospace",
                  }}>{pipelineLabel}</span>
                </div>
                <div style={{
                  fontSize: '9px', color: 'rgba(240,238,232,0.3)',
                  fontFamily: "'IBM Plex Mono', monospace", letterSpacing: '0.06em', marginTop: '1px',
                }}>
                  {articleCount > 0 ? `${articleCount} articles` : 'Awaiting data'}
                  {pipelineInfo?.started_at && ` | Last: ${new Date(pipelineInfo.started_at).toLocaleTimeString('en-IN', {hour: '2-digit', minute: '2-digit'})}`}
                </div>
              </div>
            </div>

            {/* Confidence filter */}
            <div style={{
              padding: '6px 14px', borderBottom: '1px solid rgba(255,255,255,0.05)',
              display: 'flex', alignItems: 'center', gap: '8px',
              background: 'rgba(255,255,255,0.01)', flexShrink: 0,
            }}>
              <span style={{
                fontFamily: "'IBM Plex Mono', monospace", fontSize: '8px',
                color: 'rgba(240,238,232,0.25)', letterSpacing: '0.08em', whiteSpace: 'nowrap',
              }}>CONFIDENCE</span>
              <input
                type="range" min="0" max="100" step="5"
                value={minConfidence}
                onChange={e => setMinConfidence(Number(e.target.value))}
                style={{ flex: 1, accentColor: '#F0A500', height: '2px' }}
              />
              <span style={{
                fontFamily: "'IBM Plex Mono', monospace", fontSize: '11px',
                color: '#F0A500', fontWeight: '500', minWidth: '28px', textAlign: 'right',
              }}>{minConfidence}%</span>
            </div>

            <div style={{ flex: 1, overflow: 'hidden' }}>
              <SignalFeed
                signals={filteredSignals}
                allSignalsLoaded={allSignalsLoaded}
                onSignalClick={setSelectedSignal}
                selectedSignalId={selectedSignal?.id}
                username={username}
              />
            </div>
          </div>

          {/* Middle: Knowledge Graph */}
          <div style={{
            flex: 1, minWidth: 0, position: 'relative', background: '#020508'
          }}>
            <KnowledgeGraph
              nodes={filteredGraphData.nodes}
              edges={filteredGraphData.edges}
              onNodeClick={handleNodeClick}
              searchQuery={searchQuery}
              minConfidence={minConfidence}
            />
          </div>

          {/* Resize handle */}
          <div
            onMouseDown={handleResizeStart}
            style={{
              width: '5px', cursor: 'col-resize',
              background: isResizing ? 'rgba(240,165,0,0.15)' : 'transparent',
              transition: 'background 0.15s',
              flexShrink: 0,
            }}
            onMouseEnter={e => e.target.style.background = 'rgba(240,165,0,0.1)'}
            onMouseLeave={e => { if (!isResizing) e.target.style.background = 'transparent'; }}
          />

          {/* Right Panel: Signal Detail ONLY (terminal moved to bottom) */}
          <div style={{
            width: `${rightPanelWidth}px`, flexShrink: 0,
            background: '#050A10', display: 'flex', flexDirection: 'column',
            overflow: 'hidden',
          }}>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <SignalDetail selectedSignal={selectedSignal} username={username} />
            </div>
          </div>
        </main>

        {/* Terminal — full width at bottom of dashboard, spanning all panels */}
        <MosaicTerminal
          selectedSignal={selectedSignal}
          isOpen={terminalOpen}
          onToggle={() => setTerminalOpen(prev => !prev)}
          portfolio={portfolio}
        />
      </div>

      <style>{`
        @keyframes statusPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>  {/* Modals */}
      {showOnboarding && (
        <PortfolioOnboarding onClose={handleOnboardingClose} existingPortfolio={[]} existingUsername="" />
      )}
      {showPortfolioEditor && (
        <PortfolioOnboarding onClose={handlePortfolioSave} existingPortfolio={portfolio} existingUsername={username} />
      )}
      {showBacktest && (
        <BacktestPanel onClose={() => setShowBacktest(false)} />
      )}



    </div>
  );
}
