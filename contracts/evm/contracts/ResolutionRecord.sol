// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title ResolutionRecord
 * @dev Minimal contract to store fact-checking results from Chainlink CRE.
 * Part of the Sugar Protocol Hackathon project for Chainlink Convergence 2026.
 */
contract ResolutionRecord {

    struct Resolution {
        bool verdict;
        string reasoning;
        uint256 timestamp;
    }

    // Mapping from claimId (Sui Object ID as string) to its resolution
    mapping(string => Resolution) public resolutions;

    // Event emitted when a new resolution is recorded
    event ResolutionRecorded(string claimId, bool verdict, uint256 timestamp);

    /**
     * @dev Records a resolution for a specific claim.
     * @param claimId The unique identifier for the claim (Sui ID).
     * @param verdict True if the claim is verified, false otherwise.
     * @param reasoning The technical explanation behind the verdict.
     */
    function recordResolution(
        string calldata claimId, 
        bool verdict, 
        string calldata reasoning
    ) external {
        resolutions[claimId] = Resolution({
            verdict: verdict,
            reasoning: reasoning,
            timestamp: block.timestamp
        });

        emit ResolutionRecorded(claimId, verdict, block.timestamp);
    }

    /**
     * @dev Retrieves the resolution for a specific claim.
     * @param claimId The unique identifier for the claim.
     */
    function getResolution(string calldata claimId) external view returns (Resolution memory) {
        return resolutions[claimId];
    }
}
