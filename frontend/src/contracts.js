/**
 * EVM contract helpers for PredictionMarket interaction on Sepolia Testnet.
 */
import { ethers } from 'ethers';

// Contract address — update after deployment or set VITE_PREDICTION_MARKET_ADDRESS
export const PREDICTION_MARKET_ADDRESS =
  import.meta.env.VITE_PREDICTION_MARKET_ADDRESS ||
  '0x8bB67a5c7Ca89Ee759f9f11a216Eb2921e68f7A5';

// Sepolia chain ID
export const EXPECTED_CHAIN_ID =
  Number(import.meta.env.VITE_EVM_CHAIN_ID) || 11155111;

// Minimal ABI — only the functions the frontend needs
const PREDICTION_MARKET_ABI = [
  'function createMarket(string claimId, string claimText) external payable',
  'function verifyMarket(uint256 marketId) external',
  'function getMarket(uint256 marketId) external view returns (tuple(string claimId, string claimText, address creator, uint256 stake, uint8 status, uint256 createdAt))',
  'function nextMarketId() external view returns (uint256)',
  'event MarketCreated(uint256 indexed marketId, string claimId, address creator, uint256 stake)',
  'event MarketVerified(uint256 indexed marketId)',
];

/**
 * Get an ethers Contract instance for PredictionMarket.
 * @param {ethers.Signer|ethers.Provider} signerOrProvider
 */
export function getContract(signerOrProvider) {
  return new ethers.Contract(
    PREDICTION_MARKET_ADDRESS,
    PREDICTION_MARKET_ABI,
    signerOrProvider
  );
}

/**
 * Create a new prediction market by staking ETH.
 * @param {ethers.Signer} signer - Connected wallet signer
 * @param {string} claimId - Unique claim identifier
 * @param {string} claimText - Human-readable claim description
 * @param {string} stakeEth - Amount of ETH to stake (e.g. "0.01")
 * @returns {{ txHash: string, marketId: number }}
 */
export async function createMarketTx(signer, claimId, claimText, stakeEth) {
  const contract = getContract(signer);
  const tx = await contract.createMarket(claimId, claimText, {
    value: ethers.parseEther(stakeEth),
    gasLimit: 300000,
  });
  const receipt = await tx.wait();

  // Extract marketId from MarketCreated event
  const log = receipt.logs.find((l) => {
    try {
      return contract.interface.parseLog(l)?.name === 'MarketCreated';
    } catch {
      return false;
    }
  });

  let marketId = 0;
  if (log) {
    const parsed = contract.interface.parseLog(log);
    marketId = Number(parsed.args.marketId);
  }

  return { txHash: receipt.hash, marketId };
}

/**
 * Read a market's on-chain status.
 * @param {ethers.Provider} provider
 * @param {number} marketId
 * @returns {{ claimId, claimText, creator, stake, status, createdAt }}
 */
export async function getMarketStatus(provider, marketId) {
  const contract = getContract(provider);
  const m = await contract.getMarket(marketId);
  return {
    claimId: m.claimId,
    claimText: m.claimText,
    creator: m.creator,
    stake: ethers.formatEther(m.stake),
    status: Number(m.status), // 0=PENDING, 1=VERIFIED, 2=RESOLVED
    createdAt: Number(m.createdAt),
  };
}

/**
 * Truncate an address for display: 0x1234...abcd
 */
export function truncateAddress(addr) {
  if (!addr) return '';
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}
