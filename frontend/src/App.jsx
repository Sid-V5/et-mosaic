import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import KnowledgeGraph from './components/KnowledgeGraph';
import SignalFeed from './components/SignalFeed';
import SignalDetail from './components/SignalDetail';
import PortfolioOnboarding from './components/PortfolioOnboarding';
import PipelineStatus from './components/PipelineStatus';
import BacktestPanel from './components/BacktestPanel';

const API_BASE = 'http://localhost:8000';

export default function App() {
  const [signals, setSignals] = useState([]);
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [portfolio, setPortfolio] = useState([]);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showBacktest, setShowBacktest] = useState(false);
  const [showPortfolioEditor, setShowPortfolioEditor] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Load portfolio from localStorage
  useEffect(() => {
    const stored = localStorage.getItem('et_portfolio');
    if (stored) {
      try {
        setPortfolio(JSON.parse(stored));
      } catch { setPortfolio([]); }
    } else {
      setShowOnboarding(true);
    }
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

      setSignals(sigRes.data?.signals || []);
      setGraphData(graphRes.data || { nodes: [], edges: [] });
    } catch (e) {
      console.error('Data fetch error:', e);
    }
  }, [portfolio, searchQuery]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleOnboardingClose = (tickers) => {
    setPortfolio(tickers);
    setShowOnboarding(false);
  };

  const handlePortfolioSave = (tickers) => {
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

  return (
    <div style={{
      width: '100vw', height: '100vh', overflow: 'hidden',
      background: '#0A1628', color: '#E2E8F0',
      fontFamily: "'Outfit', 'Segoe UI', sans-serif",
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Top Bar */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 20px', borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
        background: 'rgba(15, 23, 42, 0.8)', backdropFilter: 'blur(10px)',
        zIndex: 100,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <h1 style={{
            fontSize: '18px', fontWeight: '900', letterSpacing: '2px',
            background: 'linear-gradient(135deg, #4F86C6, #7B68EE)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            margin: 0,
          }}>
            ET MOSAIC
          </h1>
          <PipelineStatus />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Search */}
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search company..."
            style={{
              background: 'rgba(30, 41, 59, 0.6)', border: '1px solid rgba(148, 163, 184, 0.15)',
              borderRadius: '8px', padding: '6px 14px', color: '#E2E8F0',
              fontSize: '12px', width: '180px', outline: 'none',
            }}
          />

          {/* Portfolio Editor */}
          <button
            onClick={() => setShowPortfolioEditor(true)}
            title="Edit portfolio"
            style={{
              background: 'rgba(30, 41, 59, 0.6)', border: '1px solid rgba(148, 163, 184, 0.15)',
              borderRadius: '8px', padding: '6px 10px', color: '#94A3B8',
              cursor: 'pointer', fontSize: '14px',
            }}
          >
            ⚙️
          </button>

          {/* Backtest Button */}
          <button
            onClick={() => setShowBacktest(true)}
            style={{
              background: 'linear-gradient(135deg, rgba(226, 75, 74, 0.15), rgba(239, 159, 39, 0.15))',
              border: '1px solid rgba(226, 75, 74, 0.3)',
              borderRadius: '8px', padding: '6px 14px', color: '#E24B4A',
              cursor: 'pointer', fontSize: '11px', fontWeight: '700',
              letterSpacing: '0.3px',
            }}
          >
            Backtest: Adani 2023
          </button>
        </div>
      </header>

      {/* Main 3-Panel Layout */}
      <main style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: '55% 45%',
        gridTemplateRows: '1fr',
        overflow: 'hidden',
      }}>
        {/* Left: Knowledge Graph */}
        <div style={{
          borderRight: '1px solid var(--border-subtle)',
          position: 'relative',
        }}>
          <KnowledgeGraph
            nodes={graphData.nodes}
            edges={graphData.edges}
            onNodeClick={handleNodeClick}
            searchQuery={searchQuery}
          />
          {graphData.nodes.length === 0 && (
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'transparent',
              animation: 'slideUpFade 0.6s ease-out forwards',
            }}>
              <div style={{ 
                textAlign: 'center', 
                background: 'var(--glass)',
                padding: '40px',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-subtle)',
                backdropFilter: 'blur(20px)',
                maxWidth: '350px'
              }}>
                <div style={{ 
                  fontSize: '48px', 
                  marginBottom: '16px', 
                  opacity: 0.8,
                  animation: 'pulseSubtle 3s infinite ease-in-out'
                }}>🛰️</div>
                <div style={{ fontSize: '18px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '8px' }}>Ingesting Data...</div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                  The mosaic builder is currently analyzing articles, SEC filings, and market data to construct the knowledge graph.
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right: Signal Feed + Detail */}
        <div style={{
          display: 'grid',
          gridTemplateRows: '55% 45%',
          overflow: 'hidden',
          background: 'var(--glass)',
          backdropFilter: 'blur(10px)',
        }}>
          {/* Top Right: Signal Feed */}
          <div style={{
            borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
            overflow: 'hidden',
          }}>
            <SignalFeed
              signals={signals}
              onSignalClick={setSelectedSignal}
              selectedSignalId={selectedSignal?.id}
            />
          </div>

          {/* Bottom Right: Signal Detail */}
          <div style={{ overflow: 'hidden' }}>
            <SignalDetail selectedSignal={selectedSignal} />
          </div>
        </div>
      </main>

      {/* Modals */}
      {showOnboarding && (
        <PortfolioOnboarding onClose={handleOnboardingClose} />
      )}
      {showPortfolioEditor && (
        <PortfolioOnboarding onClose={handlePortfolioSave} />
      )}
      {showBacktest && (
        <BacktestPanel onClose={() => setShowBacktest(false)} />
      )}
    </div>
  );
}
