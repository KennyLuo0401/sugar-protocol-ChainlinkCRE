import { useState, useEffect, useCallback, useRef, Component } from 'react';
import { ethers } from 'ethers';
import { fetchGraph } from './api';
import { truncateAddress, EXPECTED_CHAIN_ID } from './contracts';
import Graph3D from './components/Graph3D';
import URLInput from './components/URLInput';
import Sidebar from './components/Sidebar';
import SearchBar from './components/SearchBar';
import FilterBar from './components/FilterBar';
import MarketPanel from './components/MarketPanel';
import Legend from './components/Legend';
import './App.css';

const ALL_TIERS = ['country', 'domain', 'event', 'organization', 'person', 'asset'];

class GraphErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(err, info) {
    console.error('[Graph3D crash]', err, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ color: '#e74c3c', padding: 40, textAlign: 'center' }}>
          Graph render error.{' '}
          <button onClick={() => this.setState({ hasError: false })} style={{ color: '#4a9eff', background: 'none', border: '1px solid #4a9eff', borderRadius: 4, padding: '4px 12px', cursor: 'pointer' }}>
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const [graphData, setGraphData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);
  const [highlightIds, setHighlightIds] = useState(null);
  const [activeTiers, setActiveTiers] = useState([...ALL_TIERS]);
  const [newNodeIds, setNewNodeIds] = useState(null);
  const prevNodeIdsRef = useRef(new Set());

  // Wallet state
  const [walletAddress, setWalletAddress] = useState(null);
  const [provider, setProvider] = useState(null);
  const [signer, setSigner] = useState(null);
  const [walletName, setWalletName] = useState(null);

  const connectWallet = useCallback(async (preferredWallet) => {
    if (!window.ethereum) {
      alert('Please install MetaMask or another EVM wallet.');
      return;
    }
    try {
      let eth = window.ethereum;
      // If multiple wallets installed, pick the one user selected
      if (window.ethereum.providers?.length) {
        if (preferredWallet === 'okx') {
          eth = window.ethereum.providers.find((p) => p.isOkxWallet || p.isOKExWallet) || eth;
        } else if (preferredWallet === 'metamask') {
          eth = window.ethereum.providers.find((p) => p.isMetaMask) || eth;
        }
      }
      const browserProvider = new ethers.BrowserProvider(eth);
      const accounts = await browserProvider.send('eth_requestAccounts', []);

      // Ensure wallet is on Sepolia
      const sepoliaHex = '0x' + EXPECTED_CHAIN_ID.toString(16);
      try {
        await eth.request({
          method: 'wallet_switchEthereumChain',
          params: [{ chainId: sepoliaHex }],
        });
      } catch (switchErr) {
        // Chain not added — add it
        if (switchErr.code === 4902) {
          await eth.request({
            method: 'wallet_addEthereumChain',
            params: [{
              chainId: sepoliaHex,
              chainName: 'Sepolia Testnet',
              nativeCurrency: { name: 'ETH', symbol: 'ETH', decimals: 18 },
              rpcUrls: ['https://ethereum-sepolia-rpc.publicnode.com'],
              blockExplorerUrls: ['https://sepolia.etherscan.io'],
            }],
          });
        } else {
          throw switchErr;
        }
      }

      // Re-create provider after chain switch
      const sepoliaProvider = new ethers.BrowserProvider(eth);
      const walletSigner = await sepoliaProvider.getSigner();
      setProvider(sepoliaProvider);
      setSigner(walletSigner);
      setWalletAddress(accounts[0]);
      setWalletName(preferredWallet === 'okx' ? 'OKX Wallet' : 'MetaMask');
    } catch (err) {
      console.error('Wallet connection failed:', err);
    }
  }, []);

  const [showWalletMenu, setShowWalletMenu] = useState(false);

  const disconnectWallet = useCallback(() => {
    setWalletAddress(null);
    setProvider(null);
    setSigner(null);
    setWalletName(null);
  }, []);

  // Listen for MetaMask account/chain changes
  useEffect(() => {
    if (!window.ethereum) return;

    const handleAccountsChanged = (accounts) => {
      if (accounts.length === 0) {
        disconnectWallet();
      } else if (walletAddress) {
        setWalletAddress(accounts[0]);
        const browserProvider = new ethers.BrowserProvider(window.ethereum);
        setProvider(browserProvider);
        browserProvider.getSigner().then(setSigner);
      }
    };

    const handleChainChanged = () => {
      if (walletAddress) {
        const browserProvider = new ethers.BrowserProvider(window.ethereum);
        setProvider(browserProvider);
        browserProvider.getSigner().then(setSigner);
      }
    };

    window.ethereum.on('accountsChanged', handleAccountsChanged);
    window.ethereum.on('chainChanged', handleChainChanged);

    return () => {
      window.ethereum.removeListener('accountsChanged', handleAccountsChanged);
      window.ethereum.removeListener('chainChanged', handleChainChanged);
    };
  }, [walletAddress, disconnectWallet]);

  const loadGraph = useCallback((silent = false) => {
    if (!silent) setLoading(true);
    return fetchGraph()
      .then((data) => {
        setGraphData(data);
        setError(null);
        return data;
      })
      .catch((err) => {
        setError(err.message);
        return null;
      })
      .finally(() => { if (!silent) setLoading(false); });
  }, []);

  useEffect(() => {
    loadGraph().then((data) => {
      if (data?.nodes) {
        prevNodeIdsRef.current = new Set(data.nodes.map((n) => n.id));
      }
    });
  }, [loadGraph]);

  const handleNodeClick = useCallback((node) => {
    setSelectedNode(node);
  }, []);

  const handleAnalyzed = useCallback(() => {
    const oldIds = prevNodeIdsRef.current;

    loadGraph(true).then((data) => {
      if (!data?.nodes) return;

      const currentIds = new Set(data.nodes.map((n) => n.id));
      const added = new Set();
      for (const id of currentIds) {
        if (!oldIds.has(id)) added.add(id);
      }

      // Update ref for next analysis
      prevNodeIdsRef.current = currentIds;

      if (added.size > 0) {
        setNewNodeIds(added);
        setTimeout(() => setNewNodeIds(null), 2000);
      }
    });
  }, [loadGraph]);

  const handleSearchResults = useCallback((results) => {
    if (!results) {
      setHighlightIds(null);
      return;
    }
    const ids = new Set();
    if (results.entities) {
      results.entities.forEach((e) => ids.add(e.canonical_id));
    }
    if (results.claims) {
      results.claims.forEach((c) => ids.add(`claim_${c.id}`));
    }
    setHighlightIds(ids.size > 0 ? ids : null);
  }, []);

  // Filter graph data by active tiers
  const filteredData = graphData
    ? {
      ...graphData,
      nodes: graphData.nodes.filter(
        (n) => n.type === 'claim' || activeTiers.includes(n.tier)
      ),
    }
    : null;

  return (
    <div className="app">
      <header className="header">
        <h1 className="brand">
          <span className="brand-sugar">SUGAR</span>
          <span className="brand-protocol">PROTOCOL</span>
          <span className="brand-subtitle">3D TIERED GENEALOGY</span>
        </h1>
        <div className="header-controls">
          <SearchBar onResults={handleSearchResults} />
          <URLInput onAnalyzed={handleAnalyzed} />
        </div>
        {graphData && (
          <span className="stats">
            <span className="stat-num">{graphData.nodes.filter(n => n.type === 'entity').length}</span> Nodes
            {' '}
            <span className="stat-num">{graphData.edges.length}</span> Links
            {' '}
            <span className="stat-num stat-articles">{graphData.article_count || 0}</span> Articles
          </span>
        )}
        {walletAddress ? (
          <button className="wallet-btn wallet-connected" onClick={disconnectWallet}>
            <span className="wallet-dot" />
            <span className="wallet-address">{truncateAddress(walletAddress)}</span>
          </button>
        ) : (
          <div className="wallet-picker-wrap">
            <button className="wallet-btn wallet-disconnected" onClick={() => setShowWalletMenu((v) => !v)}>
              Connect Wallet
            </button>
            {showWalletMenu && (
              <div className="wallet-menu">
                <button onClick={() => { setShowWalletMenu(false); connectWallet('metamask'); }}>MetaMask</button>
                <button onClick={() => { setShowWalletMenu(false); connectWallet('okx'); }}>OKX Wallet</button>
              </div>
            )}
          </div>
        )}
      </header>

      <div className="toolbar">
        <FilterBar activeTiers={activeTiers} onChange={setActiveTiers} />
      </div>

      <main className="main">
        {loading && <span className="loading">Loading graph...</span>}
        {error && <span className="error">Error: {error}</span>}
        {filteredData && !loading && (
          <GraphErrorBoundary>
            <Graph3D
              data={filteredData}
              onNodeClick={handleNodeClick}
              highlightIds={highlightIds}
              newNodeIds={newNodeIds}
            />
          </GraphErrorBoundary>
        )}
        <Sidebar node={selectedNode} onClose={() => setSelectedNode(null)} walletAddress={walletAddress} signer={signer} provider={provider} walletName={walletName} />
        <MarketPanel selectedNode={selectedNode} walletAddress={walletAddress} signer={signer} provider={provider} />
        <Legend />
      </main>
    </div>
  );
}
