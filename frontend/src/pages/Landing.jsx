import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './Landing.css';

function useCountUp(target, duration = 1500, trigger = false) {
  const [value, setValue] = useState(0);
  const rafRef = useRef(null);
  useEffect(() => {
    if (!trigger) return;
    const start = performance.now();
    const animate = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [trigger, target, duration]);
  return value;
}

function useFadeIn() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { el.classList.add('visible'); observer.unobserve(el); } },
      { threshold: 0.1 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return ref;
}

// Graph mockup node data
const MOCK_NODES = [
  { x: 72, y: 38, r: 48, color: '#FF8C00', label: 'Energy', pulse: true },
  { x: 28, y: 25, r: 32, color: '#4F86C6', label: 'Banking' },
  { x: 85, y: 72, r: 28, color: '#7B68EE', label: 'IT' },
  { x: 45, y: 78, r: 24, color: '#3CB371', label: 'Pharma' },
  { x: 18, y: 62, r: 20, color: '#CD853F', label: 'Metals' },
  { x: 60, y: 18, r: 16, color: '#FF69B4', label: 'FMCG' },
  { x: 38, y: 48, r: 14, color: '#888', label: '' },
  { x: 55, y: 55, r: 12, color: '#4F86C6', label: '' },
  { x: 82, y: 30, r: 11, color: '#FF8C00', label: '' },
  { x: 22, y: 82, r: 10, color: '#CD853F', label: '' },
  { x: 48, y: 32, r: 9, color: '#888', label: '' },
  { x: 90, y: 50, r: 8, color: '#7B68EE', label: '' },
];

const MOCK_EDGES = [
  [0, 1, 'amber'], [0, 6, 'amber'], [0, 8, 'amber'], [1, 2, 'teal'],
  [1, 4, 'teal'], [2, 7, 'teal'], [3, 5, 'teal'], [3, 9, 'teal'],
  [4, 6, 'teal'], [5, 10, 'teal'], [7, 11, 'teal'], [6, 10, 'teal'],
];

const TIMELINE_EVENTS = [
  { date: 'Jan 18', badge: 'ET MARKETS', color: '#4F86C6', title: 'FIIs pull ₹8,000 Cr from Adani group stocks' },
  { date: 'Jan 20', badge: 'ET ECONOMY', color: '#4F86C6', title: 'Adani Group debt under analyst scrutiny' },
  { date: 'Jan 21', badge: 'NSE BULK DEAL', color: '#F0A500', title: 'Large block sold in Adani Enterprises' },
  { date: 'Jan 21', badge: 'SIGNAL FIRED', color: '#3CB371', title: 'TRIPLE THREAT · 78% Confidence', glow: true },
  { date: 'Jan 25', badge: 'MARKET EVENT', color: '#E24B4A', title: 'Hindenburg report published. ₹11.5L Cr wiped.' },
];

const STEPS = [
  { n: '01', title: 'Ingest', desc: '500+ ET articles ingested from 6 channels every 15 minutes.' },
  { n: '02', title: 'Extract', desc: 'LLaMA 3.1 8B extracts entities, events, and sentiment from each article.' },
  { n: '03', title: 'Connect', desc: 'Mosaic Builder finds cross-source connections across 4 evidence layers.' },
  { n: '04', title: 'Verify', desc: 'Every signal verified against live NSE bulk deals, insider trades, and technical indicators.' },
  { n: '05', title: 'Alert', desc: 'Plain-English signal cards with Hindi audio brief. Ranked by your portfolio.' },
];

export default function Landing() {
  const navigate = useNavigate();

  // Stats count-up
  const statsRef = useRef(null);
  const [statsVisible, setStatsVisible] = useState(false);
  useEffect(() => {
    const el = statsRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setStatsVisible(true); observer.unobserve(el); } },
      { threshold: 0.1 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const stat1 = useCountUp(216, 1500, statsVisible);
  const stat2 = useCountUp(91, 1500, statsVisible);
  const stat3 = useCountUp(27, 1500, statsVisible);

  const heroRef = useFadeIn();
  const howRef = useFadeIn();
  const whatRef = useFadeIn();
  const adaniRef = useFadeIn();
  const ctaRef = useFadeIn();

  return (
    <div className="landing">
      {/* Navbar */}
      <nav className="landing-nav">
        <div className="nav-left">
          <span className="nav-dot" />
          <span className="nav-logo">ET MOSAIC</span>
        </div>
        <button className="nav-cta" onClick={() => navigate('/dashboard')}>
          Open Dashboard →
        </button>
      </nav>

      {/* Hero */}
      <section className="hero-section" ref={heroRef} data-fade>
        {/* Custom background animated SVG */}
        <div className="landing-ambient-bg">
          <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="bgGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="rgba(240,165,0,0.08)" />
                <stop offset="100%" stopColor="rgba(14,165,160,0.01)" />
              </linearGradient>
            </defs>
            <circle cx="10%" cy="20%" r="30%" fill="url(#bgGrad1)" className="ambient-blob anim-slow"/>
            <circle cx="90%" cy="80%" r="40%" fill="url(#bgGrad1)" className="ambient-blob anim-fast"/>
            <path d="M0,50 Q25,30 50,50 T100,50" fill="none" stroke="var(--accent)" strokeWidth="0.5" className="ambient-wave" opacity="0.1" />
          </svg>
        </div>

        <div className="hero-content">
          <div className="hero-left">
            <div className="hero-tag">MOSAIC THEORY · APPLIED TO INDIAN MARKETS</div>
            <h1 className="hero-headline">
              The signal hiding<br />in plain sight.
            </h1>
            <p className="hero-sub">
              ET Mosaic reads 500+ ET articles per week, cross-references them against
              live NSE filings, technical indicators, and bulk deal data - and finds the
              connections no single investor has time to find.
            </p>
            <div className="hero-stats">
              <div className="hero-stat">
                <div className="hero-stat-num">21 Cr+</div>
                <div className="hero-stat-label">DEMAT ACCOUNTS IN INDIA</div>
              </div>
              <div className="hero-stat-divider" />
              <div className="hero-stat">
                <div className="hero-stat-num">₹1.05 L Cr</div>
                <div className="hero-stat-label">RETAIL LOSSES FY25</div>
              </div>
              <div className="hero-stat-divider" />
              <div className="hero-stat">
                <div className="hero-stat-num">₹27 Lakh</div>
                <div className="hero-stat-label">BLOOMBERG COSTS PER YEAR</div>
              </div>
            </div>
            <div className="hero-cta-row">
              <button className="btn-primary" onClick={() => navigate('/dashboard')}>
                Enter the Dashboard
              </button>
              <button className="btn-ghost" onClick={() => {
                document.querySelector('.how-section')?.scrollIntoView({ behavior: 'smooth' });
              }}>
                Watch how it works →
              </button>
            </div>
          </div>

          {/* Right: graph mockup */}
          <div className="hero-right">
            <svg viewBox="0 0 100 100" className="graph-mockup" preserveAspectRatio="xMidYMid meet">
              {MOCK_EDGES.map(([from, to, type], i) => (
                <line
                  key={i}
                  x1={MOCK_NODES[from].x} y1={MOCK_NODES[from].y}
                  x2={MOCK_NODES[to].x} y2={MOCK_NODES[to].y}
                  stroke={type === 'amber' ? 'rgba(240,165,0,0.3)' : 'rgba(14,165,160,0.2)'}
                  strokeWidth="0.3"
                />
              ))}
              {MOCK_NODES.map((node, i) => (
                <g key={i}>
                  {node.pulse && (
                    <circle cx={node.x} cy={node.y} r={node.r / 6 + 2} className="pulse-ring"
                      fill="none" stroke="#F0A500" strokeWidth="0.5" />
                  )}
                  <circle cx={node.x} cy={node.y} r={node.r / 6}
                    fill={node.color} opacity="0.85"
                    className={`mock-node ${node.pulse ? 'node-glow' : ''}`}
                    style={{ animationDelay: `${i * 0.3}s` }}
                  />
                  {node.label && (
                    <text x={node.x} y={node.y + node.r / 6 + 3}
                      textAnchor="middle" className="node-label">
                      {node.label}
                    </text>
                  )}
                </g>
              ))}
            </svg>
            {/* Signal tooltip */}
            <div className="signal-tooltip">
              <span>TRIPLE THREAT · 78% confidence</span>
            </div>
          </div>
        </div>

        {/* Dashboard Preview */}
        <div className="hero-preview-container">
          <div className="hero-preview-glass">
            <img src="/dashboard-preview.png" alt="ET Mosaic Dashboard Final" className="hero-preview-image" />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="how-section" ref={howRef} data-fade>
        <div className="section-rule" />
        <div className="section-inner">
          <div className="section-tag">THE MOSAIC BUILDER PIPELINE</div>
          <div className="steps-row">
            {STEPS.map((step, i) => (
              <div key={i} className="step-card">
                <div className="step-num">{step.n}</div>
                <div className="step-title">{step.title}</div>
                <div className="step-desc">{step.desc}</div>
                {i < STEPS.length - 1 && <div className="step-arrow">→</div>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* What it is / is not */}
      <section className="what-section" ref={whatRef} data-fade>
        <div className="section-inner">
          <div className="what-grid">
            <div className="what-col">
              <h3 className="what-heading">What ET Mosaic is.</h3>
              <ul className="what-list check">
                <li><span className="check-mark">✓</span>Cross-source signal detection</li>
                <li><span className="check-mark">✓</span>Technical pattern confirmation (RSI, MACD, Bollinger)</li>
                <li><span className="check-mark">✓</span>Portfolio-aware ranking</li>
                <li><span className="check-mark">✓</span>Sector contagion detection</li>
                <li><span className="check-mark">✓</span>Hindi audio briefs for Tier 2/3 India</li>
              </ul>
            </div>
            <div className="what-col">
              <h3 className="what-heading">What it is not.</h3>
              <ul className="what-list cross">
                <li><span className="cross-mark">✗</span>Stock price prediction</li>
                <li><span className="cross-mark">✗</span>Financial advice or trade recommendations</li>
                <li><span className="cross-mark">✗</span>Insider information (100% public data only)</li>
                <li><span className="cross-mark">✗</span>A news summariser</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Adani proof */}
      <section className="adani-section" ref={adaniRef} data-fade>
        <div className="section-rule" />
        <div className="section-inner adani-inner">
          <div className="section-tag">BACK-TESTED SCENARIO</div>
          <h2 className="adani-headline">4 days before the crash.</h2>
          <p className="adani-sub">
            In January 2023, 3 ET articles and 1 NSE bulk deal anomaly converged.
            ET Mosaic would have flagged this signal on January 21st.
            Hindenburg published January 25th.
          </p>
          <div className="timeline">
            {TIMELINE_EVENTS.map((evt, i) => (
              <div key={i} className={`timeline-event ${evt.glow ? 'glow-event' : ''}`}>
                <div className="tl-line" />
                <div className="tl-dot" style={{ background: evt.color, boxShadow: evt.glow ? `0 0 12px ${evt.color}` : 'none' }} />
                <div className="tl-content">
                  <div className="tl-date">{evt.date}</div>
                  <div className="tl-badge" style={{ color: evt.color, borderColor: `${evt.color}44` }}>{evt.badge}</div>
                  <div className="tl-title">{evt.title}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="adani-disclaimer">
            Illustrative back-test based on publicly available information from January 2023. Not investment advice.
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <section className="stats-section" ref={statsRef}>
        <div className="section-inner">
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-number">{stat1 / 10} Cr</div>
              <div className="stat-label">DEMAT ACCOUNTS IN INDIA</div>
              <div className="stat-source">NSDL+CDSL, Dec 2025</div>
            </div>
            <div className="stat-item">
              <div className="stat-number">{stat2}%</div>
              <div className="stat-label">RETAIL TRADERS LOST MONEY FY25</div>
              <div className="stat-source">SEBI, Jul 2025</div>
            </div>
            <div className="stat-item">
              <div className="stat-number">₹{stat3}L</div>
              <div className="stat-label">BLOOMBERG COSTS PER SEAT/YEAR</div>
              <div className="stat-source">Godel Terminal, Jan 2025</div>
            </div>
            <div className="stat-item">
              <div className="stat-number stat-free">₹0</div>
              <div className="stat-label">ET MOSAIC OPERATING COST</div>
              <div className="stat-source">Verified</div>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="cta-section" ref={ctaRef} data-fade>
        <div className="section-inner cta-inner">
          <div className="section-tag">GET STARTED</div>
          <h2 className="cta-headline">
            See what the market<br />is hiding from you.
          </h2>
          <p className="cta-sub">
            Enter your NSE tickers. ET Mosaic handles the rest.
          </p>
          <button className="btn-primary btn-large" onClick={() => navigate('/dashboard')}>
            Open ET Mosaic →
          </button>
          <div className="cta-note">Free. No account required. ₹0 operating cost.</div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <span className="footer-logo">ET MOSAIC</span>
        <span className="footer-note">Built for ET GenAI Hackathon 2026. Track PS6 - AI for the Indian Investor.</span>
      </footer>
    </div>
  );
}
