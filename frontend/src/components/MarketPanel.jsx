import { useState, useEffect, useMemo } from 'react';
import { fetchMarkets } from '../api';

export default function MarketPanel({ selectedNode, onClose, walletAddress, signer, provider }) {
  const [markets, setMarkets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedMarketId, setExpandedMarketId] = useState(null);

  useEffect(() => {
    fetchMarkets()
      .then((data) => setMarkets(data.markets))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // 當選中 claim node 時，高亮對應 market
  const highlightedMarketId = useMemo(() => {
    if (!selectedNode || selectedNode.nodeType !== 'claim') return null;
    // 嘗試匹配 claim_id
    return markets.find(m => m.claim_id === selectedNode.id)?.id || null;
  }, [selectedNode, markets]);

  // 自動展開面板 when claim node selected
  useEffect(() => {
    if (highlightedMarketId) setIsExpanded(true);
  }, [highlightedMarketId]);

  const formatSui = (mist) => (mist / 1_000_000_000).toFixed(2);

  return (
    <div className={`market-panel ${isExpanded ? 'expanded' : 'collapsed'}`}>
      {/* 標題列 — 始終可見 */}
      <div className="market-panel-header" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="market-panel-title">🏛 Truth Markets ({markets.length})</span>
        <span className="market-panel-toggle">{isExpanded ? '▼' : '▲'}</span>
      </div>

      {/* 展開的卡片列表 */}
      {isExpanded && (
        <div className="market-panel-body">
          {loading && <div className="market-loading">Loading markets...</div>}
          {!loading && markets.length === 0 && <div className="market-loading">No markets found.</div>}
          {markets.map((m) => (
            <div
              key={m.id}
              className={`market-card ${highlightedMarketId === m.id ? 'highlighted' : ''} ${expandedMarketId === m.id ? 'detail' : ''}`}
              onClick={() => setExpandedMarketId(expandedMarketId === m.id ? null : m.id)}
            >
              {/* 問題標題 */}
              <div className="market-question">{m.question}</div>

              {/* 狀態標籤 */}
              <div className="market-status-row">
                {!m.resolved && !m.evm_verified && <span className="market-badge open">OPEN</span>}
                {!m.resolved && m.evm_verified && <span className="market-badge verified">VERIFIED</span>}
                {m.resolved && m.outcome && <span className="market-badge true">VERIFIED TRUE</span>}
                {m.resolved && !m.outcome && <span className="market-badge false">RESOLVED FALSE</span>}
                {(m.resolution?.chainlink_verified || m.evm_verified) && (
                  <span className="market-badge chainlink">Chainlink CRE</span>
                )}
              </div>

              {/* 投票進度條 */}
              <div className="market-bar-track">
                <div className="market-bar-for" style={{ width: `${m.for_percentage}%` }} />
              </div>
              <div className="market-bar-labels">
                <span className="market-for">FOR {formatSui(m.for_pool)} SUI</span>
                <span className="market-against">AGAINST {formatSui(m.against_pool)} SUI</span>
              </div>

              {/* 展開的詳細 — 只在點擊後顯示 */}
              {expandedMarketId === m.id && (
                <div className="market-detail">
                  <div className="market-detail-row">
                    <span className="market-detail-label">Deadline</span>
                    <span>{new Date(m.deadline).toLocaleDateString()}</span>
                  </div>
                  <div className="market-detail-row">
                    <span className="market-detail-label">Total Stakers</span>
                    <span>{m.total_stakers}</span>
                  </div>
                  {m.resolution && (
                    <div className="market-resolution">
                      <div className="market-detail-label">Resolution Reasoning</div>
                      <div className="market-reasoning">{m.resolution.reasoning}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
