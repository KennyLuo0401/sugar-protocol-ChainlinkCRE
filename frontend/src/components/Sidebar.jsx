import { useState } from 'react';
import { createMarketTx, getMarketStatus } from '../contracts';
import { triggerCREVerify } from '../api';

const SUI_PACKAGE_ID = '0x5f1a286c635e17504489ba7f2b00e4002f9529bb4cda58ad0b77e138c5b3da59';
const SUI_REGISTRY_ID = '0x45197aca531cb7970636fae068212c768a47ab853152df474f3e01bbd9deeab8';
const SUISCAN_BASE = 'https://suiscan.xyz/testnet';

export default function Sidebar({ node, onClose, walletAddress, signer, provider, walletName }) {
  const [stakeAmount, setStakeAmount] = useState('0.01');
  const [txStatus, setTxStatus] = useState(null); // null | 'pending' | 'confirmed' | 'verifying' | 'verified' | 'error'
  const [txHash, setTxHash] = useState(null);
  const [marketId, setMarketId] = useState(null);
  const [txError, setTxError] = useState(null);

  if (!node) return null;

  const isClaim = node.nodeType === 'claim';

  const handleCreateMarket = async () => {
    if (!signer) return;
    setTxStatus('pending');
    setTxError(null);
    setTxHash(null);
    setMarketId(null);

    try {
      const claimId = node.id || 'claim_unknown';
      const claimText = node.label || '';
      const result = await createMarketTx(signer, claimId, claimText, stakeAmount);
      setTxHash(result.txHash);
      setMarketId(result.marketId);
      setTxStatus('confirmed');

      // CRE verification: skip auto-verify so CRE simulate can demo it
      // User can click "Verify with CRE" button manually, or use CRE simulate in terminal
    } catch (err) {
      console.error('Create market failed:', err);
      setTxError(err.message || 'Transaction failed');
      setTxStatus('error');
    }
  };

  const resetTxState = () => {
    setTxStatus(null);
    setTxHash(null);
    setMarketId(null);
    setTxError(null);
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>{node.label}</h2>
        <button className="sidebar-close" onClick={onClose}>&times;</button>
      </div>
      <div className="sidebar-body">
        <div className="sidebar-field">
          <span className="sidebar-label">Type</span>
          <span className="sidebar-value">{node.nodeType}</span>
        </div>
        {node.tier && (
          <div className="sidebar-field">
            <span className="sidebar-label">Tier</span>
            <span className={`sidebar-tier tier-${node.tier}`}>{node.tier}</span>
          </div>
        )}
        {node.claimType && (
          <div className="sidebar-field">
            <span className="sidebar-label">Claim Type</span>
            <span className="sidebar-value">{node.claimType}</span>
          </div>
        )}
        {node.aliases && node.aliases.length > 0 && (
          <div className="sidebar-field">
            <span className="sidebar-label">Aliases</span>
            <span className="sidebar-value">{node.aliases.join(', ')}</span>
          </div>
        )}
        {node.sourceUrl && (
          <div className="sidebar-field">
            <span className="sidebar-label">Source</span>
            <a
              className="sidebar-link"
              href={node.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              {node.sourceUrl}
            </a>
          </div>
        )}

        {/* Create Market — only for claim nodes with connected wallet */}
        {isClaim && (
          <>
            <div className="sidebar-divider" />
            <div className="sidebar-field">
              <span className="sidebar-label">EVM Prediction Market</span>
            </div>
            {!walletAddress ? (
              <div className="create-market-hint">Connect wallet to create market</div>
            ) : txStatus === null ? (
              <div className="create-market-form">
                <div className="stake-input-row">
                  <label className="stake-label">Stake (ETH)</label>
                  <input
                    className="stake-input"
                    type="number"
                    step="0.001"
                    min="0.001"
                    value={stakeAmount}
                    onChange={(e) => setStakeAmount(e.target.value)}
                  />
                </div>
                <button className="create-market-btn" onClick={handleCreateMarket}>
                  Create Market
                </button>
              </div>
            ) : (
              <div className="create-market-status">
                {txStatus === 'pending' && (
                  <div className="tx-status tx-pending">Confirm in {walletName || 'wallet'}...</div>
                )}
                {txStatus === 'confirmed' && (
                  <div className="tx-status tx-confirmed">
                    Market #{marketId} created
                    {txHash && <div className="tx-hash" onClick={() => navigator.clipboard.writeText(txHash)} title="Click to copy">TX: {txHash}</div>}
                    <button className="create-market-btn cre-verify-btn" onClick={async () => {
                      setTxStatus('verifying');
                      try {
                        // Check if CRE simulate already verified it on-chain
                        if (provider) {
                          const status = await getMarketStatus(provider, marketId);
                          if (status.status >= 1) {
                            setTxStatus('verified');
                            return;
                          }
                        }
                        await triggerCREVerify(String(marketId));
                        setTxStatus('verified');
                      } catch {
                        // If revert, check if already verified
                        try {
                          if (provider) {
                            const status = await getMarketStatus(provider, marketId);
                            if (status.status >= 1) { setTxStatus('verified'); return; }
                          }
                        } catch { /* ignore */ }
                        setTxStatus('confirmed');
                      }
                    }}>
                      Verify with Chainlink CRE
                    </button>
                  </div>
                )}
                {txStatus === 'verifying' && (
                  <div className="tx-status tx-verifying">CRE verifying market...</div>
                )}
                {txStatus === 'verified' && (
                  <div className="tx-status tx-verified">
                    Market #{marketId} verified by Chainlink CRE
                    {txHash && <div className="tx-hash" onClick={() => navigator.clipboard.writeText(txHash)} title="Click to copy">TX: {txHash}</div>}
                  </div>
                )}
                {txStatus === 'error' && (
                  <div className="tx-status tx-error">{txError}</div>
                )}
                {(txStatus === 'confirmed' || txStatus === 'verified' || txStatus === 'error') && (
                  <button className="create-market-btn-secondary" onClick={resetTxState}>
                    {txStatus === 'error' ? 'Try Again' : 'Create Another'}
                  </button>
                )}
              </div>
            )}
          </>
        )}

        {/* Sui On-Chain Links */}
        <div className="sidebar-divider" />
        <div className="sidebar-field">
          <span className="sidebar-label">On-Chain</span>
        </div>
        <div className="sidebar-field">
          <a
            className="sidebar-link sui-link"
            href={`${SUISCAN_BASE}/object/${SUI_PACKAGE_ID}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Sugar Protocol Package
          </a>
        </div>
        <div className="sidebar-field">
          <a
            className="sidebar-link sui-link"
            href={`${SUISCAN_BASE}/object/${SUI_REGISTRY_ID}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Entity Registry
          </a>
        </div>
      </div>
    </div>
  );
}
