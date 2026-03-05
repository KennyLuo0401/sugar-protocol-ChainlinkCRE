import React from 'react';

export default function Legend() {
  return (
    <div className="legend-panel">
      <div className="legend-section">
        <div className="legend-title">ENTITY TIERS</div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#ef4444' }} />
          <span>T0 國家</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#b91c1c' }} />
          <span>T1 議題</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#f97316' }} />
          <span>T2 事件</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#a855f7' }} />
          <span>T2.5 組織</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#3b82f6' }} />
          <span>T3 人物</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#eab308' }} />
          <span>資產 Asset</span>
        </div>
      </div>

      <div className="legend-section">
        <div className="legend-title">CLAIMS</div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#22c55e' }} />
          <span>立場 Stance</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#4ade80' }} />
          <span>事實 Factual</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#fbbf24' }} />
          <span>觀點 Opinion</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#8b5cf6' }} />
          <span>預測 Prediction</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot" style={{ background: '#3b82f6' }} />
          <span>佐證 Evidence</span>
        </div>
      </div>

      <div className="legend-section">
        <div className="legend-title">EDGES</div>
        <div className="legend-item">
          <span className="legend-line" style={{ background: '#4a9eff' }} />
          <span>包含 Contains</span>
        </div>
        <div className="legend-item">
          <span className="legend-line" style={{ background: '#22c55e' }} />
          <span>支持 Supports</span>
        </div>
        <div className="legend-item">
          <span className="legend-line" style={{ background: '#ef4444' }} />
          <span>矛盾 Contradicts</span>
        </div>
        <div className="legend-item">
          <span className="legend-line" style={{ background: '#f97316' }} />
          <span>因果 Causal</span>
        </div>
      </div>
      
      <div className="legend-keybinds">
        drag = rotate · scroll = zoom · hover = info · click = focus
      </div>
    </div>
  );
}
