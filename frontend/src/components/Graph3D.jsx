import { useRef, useCallback, useMemo, useEffect, useState } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import SpriteText from 'three-spritetext';
import * as THREE from 'three';

// Tier → Y-axis height (from PROJECT_STATUS.md)
const TIER_Y = {
  country: 140,
  domain: 80,
  event: 20,
  organization: -20,
  person: -60,
  asset: -40,
};
const CLAIM_Y = -130;

// Entity Tier 顏色
const TIER_COLOR = {
  country: '#ef4444',      // T0 Red
  domain: '#b91c1c',       // T1 Dark Red
  event: '#f97316',        // T2 Orange
  organization: '#a855f7', // T2.5 Purple
  person: '#3b82f6',       // T3 Blue
  asset: '#eab308',        // Asset Yellow
};

// Claim 類型顏色
const CLAIM_COLOR = {
  stance: '#22c55e',       // Stance Green
  factual: '#4ade80',      // Factual Light Green
  opinion: '#fbbf24',      // Opinion Gold
  prediction: '#8b5cf6',   // Prediction Violet
  evidence: '#3b82f6',     // Evidence Blue
};

// Tier → node size
const TIER_SIZE = {
  country: 12,
  domain: 10,
  event: 8,
  organization: 7,
  person: 6,
  asset: 6,
};
const CLAIM_SIZE = 4;

// Edge 顏色
const EDGE_COLOR = {
  supports: '#22c55e',
  corroborates: '#22c55e',
  contains: '#4a9eff',
  contradicts: '#ef4444',
  causal: '#f97316',
  related: '#666',
};

const ANIM_DURATION = 2000; // ms

function transformData(apiData, newNodeIds) {
  if (!apiData) return { nodes: [], links: [] };

  const nodeIds = new Set(apiData.nodes.map((n) => n.id));

  const nodes = apiData.nodes.map((n) => {
    const isNew = newNodeIds?.has(n.id);
    return {
      id: n.id,
      label: n.label,
      nodeType: n.type,           // "entity" or "claim"
      tier: n.tier || null,
      claimType: n.claim_type || null,
      isNew,
      // New nodes start at (0,0,0) — no fixed Y initially, let them fly in
      fy: isNew ? undefined : (n.type === 'entity' ? (TIER_Y[n.tier] ?? 0) : CLAIM_Y),
      // Store target Y for animation
      _targetFy: n.type === 'entity' ? (TIER_Y[n.tier] ?? 0) : CLAIM_Y,
    };
  });

  // Only include edges where both source and target exist
  const links = apiData.edges
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => ({
      source: e.source,
      target: e.target,
      edgeType: e.type,
    }));

  return { nodes, links };
}

export default function Graph3D({ data, onNodeClick, highlightIds, newNodeIds }) {
  const fgRef = useRef();
  const [animFactor, setAnimFactor] = useState(1); // 0→1 over ANIM_DURATION
  const animStartRef = useRef(null);
  const rafRef = useRef(null);

  // Run scale-in animation when newNodeIds changes
  useEffect(() => {
    if (!newNodeIds || newNodeIds.size === 0) {
      setAnimFactor(1);
      return;
    }

    setAnimFactor(0);
    animStartRef.current = performance.now();

    const animate = (now) => {
      const elapsed = now - animStartRef.current;
      const t = Math.min(elapsed / ANIM_DURATION, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      setAnimFactor(eased);

      if (t < 1) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        // Animation done — fix Y positions for new nodes
        const fg = fgRef.current;
        if (fg && typeof fg.graphData === 'function') {
          const gd = fg.graphData();
          gd.nodes.forEach((node) => {
            if (newNodeIds.has(node.id) && node._targetFy !== undefined) {
              node.fy = node._targetFy;
            }
          });
        }
      }
    };

    // Set initial positions for new nodes to (0,0,0)
    const fg = fgRef.current;
    if (fg && typeof fg.graphData === 'function') {
      const gd = fg.graphData();
      gd.nodes.forEach((node) => {
        if (newNodeIds.has(node.id)) {
          node.x = 0;
          node.y = 0;
          node.z = 0;
        }
      });
    }

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [newNodeIds]);

  const graphData = useMemo(
    () => transformData(data, newNodeIds),
    [data, newNodeIds]
  );

  const handleNodeClick = useCallback(
    (node) => {
      if (onNodeClick) onNodeClick(node);

      // Fly camera to clicked node
      const fg = fgRef.current;
      if (fg && typeof fg.cameraPosition === 'function') {
        const distance = 200;
        const { x, y, z } = node;
        fg.cameraPosition(
          { x, y: y + distance * 0.3, z: z + distance },
          { x, y, z },
          1000
        );
      }
    },
    [onNodeClick]
  );

  return (
    <ForceGraph3D
      ref={fgRef}
      graphData={graphData}
      backgroundColor="#050505"
      showNavInfo={true}
      nodeThreeObjectExtend={true}
      // Nodes
      nodeLabel={(node) => `[${node.tier || node.claimType || 'Claim'}] ${node.label}`}
      nodeThreeObject={(node) => {
        const isClaim = node.nodeType === 'claim';
        const color = isClaim
          ? (CLAIM_COLOR[node.claimType] || '#999')
          : (TIER_COLOR[node.tier] || '#fff');

        let size = isClaim ? CLAIM_SIZE : (TIER_SIZE[node.tier] || 5);
        if (highlightIds && highlightIds.has(node.id)) {
          size *= 1.5;
        }

        // Highlight / dim 邏輯
        const dimmed = highlightIds && !highlightIds.has(node.id);
        const opacity = dimmed ? 0.15 : 0.95;

        // Scale-in for new nodes
        const scale = node.isNew ? animFactor : 1;

        // 球體
        const geometry = new THREE.SphereGeometry(size * scale);
        const material = new THREE.MeshPhongMaterial({
          color: color,
          transparent: true,
          opacity: opacity,
          shininess: 100,
          emissive: color,
          emissiveIntensity: dimmed ? 0.05 : 0.25,
        });
        const sphere = new THREE.Mesh(geometry, material);

        // Entity 節點加文字標籤（Claim 太多不加）
        if (!isClaim && !dimmed) {
          const label = new SpriteText(node.label);
          label.color = '#ffffff';
          label.textHeight = 3;
          label.fontFace = 'sans-serif';
          label.backgroundColor = 'rgba(0,0,0,0.5)';
          label.padding = 1;
          label.borderRadius = 2;
          label.position.set(0, size + 4, 0);
          sphere.add(label);
        }

        return sphere;
      }}
      // Edges
      linkColor={(link) => EDGE_COLOR[link.edgeType] || '#444'}
      linkWidth={1.5}
      linkOpacity={0.6}
      linkDirectionalParticles={(link) =>
        link.edgeType === 'contradicts' ? 3 : 2
      }
      linkDirectionalParticleSpeed={0.005}
      linkDirectionalParticleWidth={3}
      linkDirectionalParticleColor={(link) => EDGE_COLOR[link.edgeType] || '#fff'}
      linkCurvature={0.1}
      linkCurveRotation={0.5}
      // Interaction
      onNodeClick={handleNodeClick}
      // Force engine: only constrain Y, let X/Z spread naturally
      d3AlphaDecay={0.02}
      d3VelocityDecay={0.3}
    />
  );
}

