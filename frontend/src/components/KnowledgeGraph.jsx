import { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import * as d3 from 'd3';

const SECTOR_COLORS = {
  Banking: '#4F86C6',
  IT: '#7B68EE',
  Metals: '#CD853F',
  Energy: '#FF8C00',
  Pharma: '#3CB371',
  FMCG: '#FF69B4',
  Auto: '#E06666',
  Infra: '#8B4513',
  NBFC: '#6495ED',
  Telecom: '#20B2AA',
  Technology: '#9370DB',
  Financials: '#4682B4',
  Healthcare: '#2E8B57',
  Industrials: '#B8860B',
  Consumer: '#DB7093',
  Utilities: '#778899',
  Defence: '#556B2F',
  RealEstate: '#A0522D',
  'Oil & Gas': '#D2691E',
  Unknown: '#6B7280',
  Other: '#6B7280',
};

const SEVERITY_COLORS = {
  high: '#E24B4A',
  medium: '#EF9F27',
  low: 'rgba(148, 163, 184, 0.4)',
};

// Sector positions for clustering (normalized 0-1 then scaled)
const SECTOR_POSITIONS = {
  Banking: { x: 0.12, y: 0.25 },
  Financials: { x: 0.18, y: 0.42 },
  NBFC: { x: 0.08, y: 0.5 },
  IT: { x: 0.78, y: 0.15 },
  Technology: { x: 0.85, y: 0.3 },
  Telecom: { x: 0.9, y: 0.45 },
  Energy: { x: 0.45, y: 0.1 },
  'Oil & Gas': { x: 0.35, y: 0.12 },
  Metals: { x: 0.25, y: 0.12 },
  Pharma: { x: 0.65, y: 0.75 },
  Healthcare: { x: 0.72, y: 0.85 },
  Auto: { x: 0.22, y: 0.78 },
  FMCG: { x: 0.45, y: 0.82 },
  Consumer: { x: 0.38, y: 0.88 },
  Infra: { x: 0.12, y: 0.72 },
  Industrials: { x: 0.1, y: 0.6 },
  Defence: { x: 0.55, y: 0.35 },
  RealEstate: { x: 0.55, y: 0.6 },
  Utilities: { x: 0.68, y: 0.55 },
  Unknown: { x: 0.5, y: 0.5 },
  Other: { x: 0.5, y: 0.5 },
};

function getRadius(d) {
  if (d.type === 'sector') return 24;
  if (d.type === 'company') return 16;
  return Math.min(7 + (d.connections_count || 0) * 2.5, 18);
}

export default function KnowledgeGraph({ nodes = [], edges = [], onNodeClick, searchQuery = '' }) {
  const containerRef = useRef(null);
  const svgRef = useRef(null);
  const tooltipRef = useRef(null);
  const simRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [activeSector, setActiveSector] = useState(null); // for sector filter
  const [severityFilter, setSeverityFilter] = useState({ high: true, medium: true, low: true });

  // Get all unique sectors present in the data
  const presentSectors = useMemo(() =>
    [...new Set(nodes.map(n => n.sector).filter(s => s && s !== 'Other' && s !== 'Unknown'))].sort(),
    [nodes]
  );

  // Filter nodes and edges based on active sector and search
  const { filteredNodes, filteredEdges } = useMemo(() => {
    let fn = nodes;
    let fe = edges;

    // Sector filter
    if (activeSector) {
      const sectorNodeIds = new Set(fn.filter(n => n.sector === activeSector).map(n => n.id));
      fn = fn.filter(n => sectorNodeIds.has(n.id));
      fe = fe.filter(e => {
        const sId = typeof e.source === 'object' ? e.source.id : e.source;
        const tId = typeof e.target === 'object' ? e.target.id : e.target;
        return sectorNodeIds.has(sId) && sectorNodeIds.has(tId);
      });
    }

    // Search filter — highlight matching nodes
    if (searchQuery && searchQuery.length >= 2) {
      const q = searchQuery.toLowerCase();
      const matchingIds = new Set(fn.filter(n =>
        n.label?.toLowerCase().includes(q) ||
        n.id?.toLowerCase().includes(q) ||
        n.sector?.toLowerCase().includes(q)
      ).map(n => n.id));

      // Also include nodes connected to matching nodes
      fe.forEach(e => {
        const sId = typeof e.source === 'object' ? e.source.id : e.source;
        const tId = typeof e.target === 'object' ? e.target.id : e.target;
        if (matchingIds.has(sId)) matchingIds.add(tId);
        if (matchingIds.has(tId)) matchingIds.add(sId);
      });

      fn = fn.filter(n => matchingIds.has(n.id));
      fe = fe.filter(e => {
        const sId = typeof e.source === 'object' ? e.source.id : e.source;
        const tId = typeof e.target === 'object' ? e.target.id : e.target;
        return matchingIds.has(sId) && matchingIds.has(tId);
      });
    }

    // Severity filter on edges
    fe = fe.filter(e => {
      const sev = (e.severity || 'low').toLowerCase();
      return severityFilter[sev] !== false;
    });

    return { filteredNodes: fn, filteredEdges: fe };
  }, [nodes, edges, activeSector, searchQuery, severityFilter]);

  // ResizeObserver for responsive sizing
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) setDimensions({ width, height });
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // Main D3 rendering
  useEffect(() => {
    if (!svgRef.current || filteredNodes.length === 0) return;

    const { width, height } = dimensions;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    // Deep copy data for D3 mutation
    const nodesCopy = filteredNodes.map(d => ({ ...d }));
    const edgesCopy = filteredEdges.map(d => ({ ...d }));

    // Build adjacency map
    const adjacencyMap = new Map();
    edgesCopy.forEach(e => {
      const sId = typeof e.source === 'object' ? e.source.id : e.source;
      const tId = typeof e.target === 'object' ? e.target.id : e.target;
      if (!adjacencyMap.has(sId)) adjacencyMap.set(sId, new Set());
      if (!adjacencyMap.has(tId)) adjacencyMap.set(tId, new Set());
      adjacencyMap.get(sId).add(tId);
      adjacencyMap.get(tId).add(sId);
    });

    // Main SVG group with zoom
    const g = svg.append('g');

    const zoom = d3.zoom()
      .scaleExtent([0.2, 5])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });
    svg.call(zoom);

    // Set initial zoom
    const initialScale = Math.min(width, height) / 900;
    svg.call(zoom.transform, d3.zoomIdentity
      .translate(width / 2, height / 2)
      .scale(Math.max(initialScale, 0.5))
      .translate(-width / 2, -height / 2)
    );

    // Defs: glow filter
    const defs = svg.append('defs');
    const glowFilter = defs.append('filter')
      .attr('id', 'glow')
      .attr('x', '-50%').attr('y', '-50%')
      .attr('width', '200%').attr('height', '200%');
    glowFilter.append('feGaussianBlur')
      .attr('stdDeviation', '4')
      .attr('result', 'coloredBlur');
    const feMerge = glowFilter.append('feMerge');
    feMerge.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    // Force simulation — tuned for larger 500+ node graphs
    const sim = d3.forceSimulation(nodesCopy)
      .force('link', d3.forceLink(edgesCopy)
        .id(d => d.id)
        .distance(d => {
          if (d.label === 'sector') return 120;
          if (d.label === 'entity' || d.label === 'company_sector') return 160;
          return 280;
        })
        .strength(d => {
          if (d.label === 'sector') return 0.6;
          if (d.label === 'entity') return 0.4;
          return 0.15;
        })
      )
      .force('charge', d3.forceManyBody()
        .strength(d => {
          if (d.type === 'sector') return -2000;
          if (d.type === 'company') return -800;
          return -400;
        })
        .distanceMax(800)
      )
      .force('center', d3.forceCenter(width / 2, height / 2).strength(0.01))
      // Strong collision detection — nodes CANNOT overlap edges
      .force('collide', d3.forceCollide(d => getRadius(d) + 30).iterations(4).strength(1))
      // Gentle sector clustering — organic feel, not boxy grid
      .force('clusterX', d3.forceX(d => {
        const pos = SECTOR_POSITIONS[d.sector] || SECTOR_POSITIONS.Other;
        return pos.x * width;
      }).strength(d => d.type === 'sector' ? 0.04 : 0.01))
      .force('clusterY', d3.forceY(d => {
        const pos = SECTOR_POSITIONS[d.sector] || SECTOR_POSITIONS.Other;
        return pos.y * height;
      }).strength(d => d.type === 'sector' ? 0.04 : 0.01))
      // Very gentle boundary — lets graph breathe
      .force('boundX', d3.forceX(width / 2).strength(0.002))
      .force('boundY', d3.forceY(height / 2).strength(0.002));

    simRef.current = sim;

    // Edges
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(edgesCopy)
      .join('line')
      .attr('stroke', d => SEVERITY_COLORS[d.severity] || SEVERITY_COLORS.low)
      .attr('stroke-width', d => {
        if (d.severity === 'high') return 2.5;
        if (d.severity === 'medium') return 1.8;
        return 0.6;
      })
      .attr('stroke-opacity', d => {
        if (d.severity === 'high') return 0.9;
        if (d.severity === 'medium') return 0.5;
        return 0.15;
      })
      .attr('stroke-dasharray', d => d.severity === 'high' ? '6,3' : 'none');

    // Nodes
    const nodeGroup = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(nodesCopy)
      .join('g')
      .attr('cursor', 'pointer')
      .style('opacity', 0);

    // Animate in
    nodeGroup.transition()
      .duration(600)
      .delay((d, i) => Math.min(i * 10, 500))
      .style('opacity', 1);

    // Outer glow ring for sector hubs
    nodeGroup.filter(d => d.type === 'sector')
      .append('circle')
      .attr('r', d => getRadius(d) + 6)
      .attr('fill', 'none')
      .attr('stroke', d => SECTOR_COLORS[d.sector] || SECTOR_COLORS.Other)
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.3)
      .attr('filter', 'url(#glow)');

    // Main circle
    nodeGroup.append('circle')
      .attr('r', d => getRadius(d))
      .attr('fill', d => SECTOR_COLORS[d.sector] || SECTOR_COLORS.Other)
      .attr('fill-opacity', d => {
        if (d.type === 'sector') return 1;
        if (d.type === 'company') return 0.92;
        return 0.8;
      })
      .attr('stroke', d => {
        if (d.type === 'sector') return '#fff';
        if (d.type === 'company') return 'rgba(255,255,255,0.6)';
        return 'rgba(255,255,255,0.12)';
      })
      .attr('stroke-width', d => {
        if (d.type === 'sector') return 2.5;
        if (d.type === 'company') return 1.5;
        return 0.5;
      });

    // Labels on sector hubs and company nodes
    nodeGroup.filter(d => d.type === 'sector')
      .append('text')
      .text(d => d.label)
      .attr('text-anchor', 'middle')
      .attr('dy', d => getRadius(d) + 18)
      .attr('fill', d => SECTOR_COLORS[d.sector] || '#94A3B8')
      .attr('font-size', '11px')
      .attr('font-weight', '700')
      .attr('font-family', "'Outfit', sans-serif")
      .attr('letter-spacing', '0.5px')
      .attr('paint-order', 'stroke')
      .attr('stroke', '#0A1628')
      .attr('stroke-width', '3px');

    nodeGroup.filter(d => d.type === 'company')
      .append('text')
      .text(d => d.label.length > 15 ? d.label.slice(0, 14) + '…' : d.label)
      .attr('text-anchor', 'middle')
      .attr('dy', d => getRadius(d) + 14)
      .attr('fill', '#CBD5E1')
      .attr('font-size', '9px')
      .attr('font-weight', '600')
      .attr('font-family', "'Outfit', sans-serif")
      .attr('paint-order', 'stroke')
      .attr('stroke', '#0A1628')
      .attr('stroke-width', '2.5px');

    // Drag behavior
    const drag = d3.drag()
      .on('start', (event, d) => {
        if (!event.active) sim.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event, d) => {
        if (!event.active) sim.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });
    nodeGroup.call(drag);

    // Tooltip + hover highlighting
    const tooltip = d3.select(tooltipRef.current);

    nodeGroup.on('mouseover', function(event, d) {
      const neighbors = adjacencyMap.get(d.id) || new Set();

      nodeGroup.transition().duration(200)
        .style('opacity', n => {
          if (n.id === d.id) return 1;
          if (neighbors.has(n.id)) return 1;
          return 0.08;
        });

      link.transition().duration(200)
        .attr('stroke-opacity', l => {
          const sId = typeof l.source === 'object' ? l.source.id : l.source;
          const tId = typeof l.target === 'object' ? l.target.id : l.target;
          if (sId === d.id || tId === d.id) return 0.9;
          return 0.03;
        })
        .attr('stroke-width', l => {
          const sId = typeof l.source === 'object' ? l.source.id : l.source;
          const tId = typeof l.target === 'object' ? l.target.id : l.target;
          if (sId === d.id || tId === d.id) return 3;
          return 0.3;
        });

      // Tooltip
      const [mx, my] = d3.pointer(event, containerRef.current);
      tooltip
        .style('display', 'block')
        .style('left', `${mx + 18}px`)
        .style('top', `${my - 10}px`)
        .html(`
          <div style="font-weight:700;margin-bottom:5px;font-size:13px;color:#F8FAFC;">${d.label || d.id}</div>
          <div style="font-size:11px;color:#94A3B8;margin-bottom:2px;">
            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${SECTOR_COLORS[d.sector] || SECTOR_COLORS.Other};margin-right:5px;vertical-align:middle;"></span>
            ${d.sector}${d.type !== 'article' ? ` · ${d.type.toUpperCase()}` : ''}
          </div>
          ${d.confidence ? `<div style="font-size:11px;color:#94A3B8;">Confidence: <span style="color:${d.confidence > 70 ? '#E24B4A' : d.confidence > 50 ? '#EF9F27' : '#3CB371'};font-weight:600;">${d.confidence}%</span></div>` : ''}
          ${d.metadata?.source ? `<div style="font-size:10px;color:#64748B;margin-top:3px;">Source: ${d.metadata.source}</div>` : ''}
          <div style="font-size:10px;color:#475569;margin-top:4px;">${(adjacencyMap.get(d.id) || new Set()).size} connections</div>
        `);
    })
    .on('mouseout', function() {
      nodeGroup.transition().duration(300).style('opacity', 1);
      link.transition().duration(300)
        .attr('stroke-opacity', d => {
          if (d.severity === 'high') return 0.9;
          if (d.severity === 'medium') return 0.5;
          return 0.15;
        })
        .attr('stroke-width', d => {
          if (d.severity === 'high') return 2.5;
          if (d.severity === 'medium') return 1.8;
          return 0.6;
        });
      tooltip.style('display', 'none');
    })
    .on('click', (event, d) => {
      if (onNodeClick) onNodeClick(d);
    });

    // Tick
    sim.on('tick', () => {

      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      nodeGroup.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    sim.alpha(1).restart();

    return () => sim.stop();
  }, [filteredNodes, filteredEdges, dimensions, onNodeClick]);

  // Stats
  const articleCount = filteredNodes.filter(n => n.type === 'article').length;

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        style={{
          background: 'radial-gradient(ellipse at 50% 50%, #0D1B2A 0%, #050B14 70%)',
          borderRadius: '12px',
          display: 'block',
        }}
      />

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        style={{
          display: 'none',
          position: 'absolute',
          background: 'rgba(10, 18, 40, 0.96)',
          border: '1px solid rgba(148, 163, 184, 0.2)',
          borderRadius: '10px',
          padding: '12px 16px',
          color: '#E2E8F0',
          fontSize: '12px',
          pointerEvents: 'none',
          zIndex: 20,
          maxWidth: '280px',
          backdropFilter: 'blur(12px)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}
      />

      {/* Top-left stats pill */}
      <div style={{
        position: 'absolute',
        top: '12px',
        left: '12px',
        display: 'flex',
        gap: '12px',
        padding: '8px 14px',
        background: 'rgba(10, 18, 40, 0.85)',
        borderRadius: '10px',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(148, 163, 184, 0.1)',
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '16px', fontWeight: '800', color: '#F8FAFC' }}>{articleCount}</div>
          <div style={{ fontSize: '9px', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.8px', fontWeight: '600' }}>Articles</div>
        </div>
        <div style={{ width: '1px', background: 'rgba(148, 163, 184, 0.15)' }} />
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '16px', fontWeight: '800', color: '#F8FAFC' }}>{filteredEdges.length}</div>
          <div style={{ fontSize: '9px', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.8px', fontWeight: '600' }}>Connections</div>
        </div>
        <div style={{ width: '1px', background: 'rgba(148, 163, 184, 0.15)' }} />
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '16px', fontWeight: '800', color: '#F8FAFC' }}>{presentSectors.length}</div>
          <div style={{ fontSize: '9px', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.8px', fontWeight: '600' }}>Sectors</div>
        </div>
      </div>

      {/* Zoom hint */}
      <div style={{
        position: 'absolute',
        top: '12px',
        right: '12px',
        padding: '6px 10px',
        background: 'rgba(10, 18, 40, 0.7)',
        borderRadius: '6px',
        fontSize: '10px',
        color: '#475569',
        backdropFilter: 'blur(4px)',
      }}>
        Scroll to zoom · Drag to pan
      </div>

      {/* Sector Filter Bar */}
      <div style={{
        position: 'absolute',
        top: '56px',
        left: '12px',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '4px',
        maxWidth: '55%',
      }}>
        <button
          onClick={() => setActiveSector(null)}
          style={{
            padding: '3px 10px', borderRadius: '12px', border: 'none',
            cursor: 'pointer', fontSize: '9px', fontWeight: '600',
            background: !activeSector ? 'rgba(79, 134, 198, 0.4)' : 'rgba(10, 18, 40, 0.7)',
            color: !activeSector ? '#F8FAFC' : '#64748B',
            backdropFilter: 'blur(4px)',
            transition: 'all 0.2s ease',
          }}
        >
          All
        </button>
        {presentSectors.map(sector => (
          <button
            key={sector}
            onClick={() => setActiveSector(activeSector === sector ? null : sector)}
            style={{
              padding: '3px 10px', borderRadius: '12px', border: 'none',
              cursor: 'pointer', fontSize: '9px', fontWeight: '600',
              display: 'flex', alignItems: 'center', gap: '4px',
              background: activeSector === sector ? `${SECTOR_COLORS[sector]}40` : 'rgba(10, 18, 40, 0.7)',
              color: activeSector === sector ? '#F8FAFC' : '#94A3B8',
              backdropFilter: 'blur(4px)',
              transition: 'all 0.2s ease',
            }}
          >
            <span style={{
              width: '6px', height: '6px', borderRadius: '50%',
              background: SECTOR_COLORS[sector] || SECTOR_COLORS.Other,
              display: 'inline-block',
            }} />
            {sector}
          </button>
        ))}
      </div>


      {/* Severity filter legend */}
      <div style={{
        position: 'absolute',
        bottom: '12px',
        right: '12px',
        display: 'flex',
        gap: '10px',
        padding: '6px 12px',
        background: 'rgba(10, 18, 40, 0.85)',
        borderRadius: '8px',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(148, 163, 184, 0.1)',
      }}>
        {[['High', '#E24B4A'], ['Medium', '#EF9F27'], ['Low', 'rgba(148,163,184,0.5)']].map(([label, color]) => {
          const key = label.toLowerCase();
          const isActive = severityFilter[key];
          return (
            <div 
              key={label} 
              onClick={() => setSeverityFilter(prev => ({ ...prev, [key]: !prev[key] }))}
              style={{ 
                display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer',
                opacity: isActive ? 1 : 0.4, transition: 'opacity 0.2s ease'
              }}
            >
              <div style={{ width: '14px', height: '2px', background: color, borderRadius: '1px' }} />
              <span style={{ fontSize: '9px', color: '#64748B', fontWeight: '500' }}>{label}</span>
            </div>
          );
        })}
      </div>

      {/* Active filter indicator */}
      {(activeSector || (searchQuery && searchQuery.length >= 2)) && (
        <div style={{
          position: 'absolute',
          bottom: '48px',
          left: '50%',
          transform: 'translateX(-50%)',
          padding: '4px 14px',
          background: 'rgba(79, 134, 198, 0.2)',
          borderRadius: '16px',
          border: '1px solid rgba(79, 134, 198, 0.3)',
          backdropFilter: 'blur(4px)',
          fontSize: '10px',
          color: '#94A3B8',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}>
          🔍 Showing {filteredNodes.length} of {nodes.length} nodes
          {activeSector && <span style={{ color: SECTOR_COLORS[activeSector], fontWeight: '700' }}>· {activeSector}</span>}
          {searchQuery && searchQuery.length >= 2 && <span>· "{searchQuery}"</span>}
          <span
            onClick={() => { setActiveSector(null); }}
            style={{ cursor: 'pointer', color: '#E24B4A', fontWeight: '700', marginLeft: '4px' }}
          >✕</span>
        </div>
      )}
    </div>
  );
}
