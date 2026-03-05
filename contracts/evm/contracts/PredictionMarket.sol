// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title PredictionMarket
 * @dev Simplified prediction market on EVM for Sugar Protocol.
 * Emits events for Chainlink CRE to monitor and verify claims.
 */
contract PredictionMarket {

    enum MarketStatus { PENDING, VERIFIED, RESOLVED }

    struct Market {
        string claimId;
        string claimText;
        address creator;
        uint256 stake;
        MarketStatus status;
        uint256 createdAt;
    }

    address public owner;
    uint256 public nextMarketId;
    mapping(uint256 => Market) public markets;

    event MarketCreated(uint256 indexed marketId, string claimId, address creator, uint256 stake);
    event MarketVerified(uint256 indexed marketId);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this");
        _;
    }

    constructor() {
        owner = msg.sender;
        nextMarketId = 1;
    }

    /**
     * @dev Create a new prediction market by staking some ETH.
     * @param claimId The unique ID of the claim.
     * @param claimText The description of the claim.
     */
    function createMarket(string calldata claimId, string calldata claimText) external payable {
        require(msg.value > 0, "Stake must be greater than zero");

        uint256 marketId = nextMarketId++;
        markets[marketId] = Market({
            claimId: claimId,
            claimText: claimText,
            creator: msg.sender,
            stake: msg.value,
            status: MarketStatus.PENDING,
            createdAt: block.timestamp
        });

        emit MarketCreated(marketId, claimId, msg.sender, msg.value);
    }

    /**
     * @dev Marks a market as verified. Called by CRE via the owner account.
     * @param marketId The ID of the market to verify.
     */
    function verifyMarket(uint256 marketId) external onlyOwner {
        require(marketId > 0 && marketId < nextMarketId, "Invalid market ID");
        Market storage market = markets[marketId];
        require(market.status == MarketStatus.PENDING, "Market not in PENDING status");

        market.status = MarketStatus.VERIFIED;
        emit MarketVerified(marketId);
    }

    /**
     * @dev Get market details.
     * @param marketId The ID of the market to retrieve.
     */
    function getMarket(uint256 marketId) external view returns (Market memory) {
        require(marketId > 0 && marketId < nextMarketId, "Invalid market ID");
        return markets[marketId];
    }
}
