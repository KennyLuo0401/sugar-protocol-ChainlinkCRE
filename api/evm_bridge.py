"""EVM bridge for Sugar Protocol — web3.py wrapper for ResolutionRecord + PredictionMarket on Sepolia."""

import os
import logging

from web3 import Web3

logger = logging.getLogger(__name__)

EVM_RPC_URL = os.environ.get(
    "EVM_RPC_URL",
    "https://ethereum-sepolia-rpc.publicnode.com",
)
EVM_PRIVATE_KEY = os.environ.get("EVM_PRIVATE_KEY", "")
RESOLUTION_CONTRACT_ADDRESS = os.environ.get(
    "RESOLUTION_CONTRACT_ADDRESS",
    "0xCbD2fc2974a121EB373b89B6B9dFa0a1D863e550",
)
PREDICTION_MARKET_ADDRESS = os.environ.get("PREDICTION_MARKET_ADDRESS", "0x8bB67a5c7Ca89Ee759f9f11a216Eb2921e68f7A5")

# Minimal ABI for ResolutionRecord contract
RESOLUTION_ABI = [
    {
        "inputs": [
            {"name": "claimId", "type": "string"},
            {"name": "verdict", "type": "bool"},
            {"name": "reasoning", "type": "string"},
        ],
        "name": "recordResolution",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "claimId", "type": "string"}],
        "name": "getResolution",
        "outputs": [
            {
                "components": [
                    {"name": "verdict", "type": "bool"},
                    {"name": "reasoning", "type": "string"},
                    {"name": "timestamp", "type": "uint256"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "name": "claimId", "type": "string"},
            {"indexed": False, "name": "verdict", "type": "bool"},
            {"indexed": False, "name": "timestamp", "type": "uint256"},
        ],
        "name": "ResolutionRecorded",
        "type": "event",
    },
]


def _get_web3() -> Web3:
    """Create a Web3 instance connected to the configured RPC."""
    return Web3(Web3.HTTPProvider(EVM_RPC_URL))


def _get_contract(w3: Web3):
    """Get the ResolutionRecord contract instance."""
    return w3.eth.contract(
        address=Web3.to_checksum_address(RESOLUTION_CONTRACT_ADDRESS),
        abi=RESOLUTION_ABI,
    )


async def record_resolution(claim_id: str, verdict: bool, reasoning: str) -> dict:
    """
    Write a resolution to the ResolutionRecord contract.

    Returns: {"success": bool, "tx_hash": str, "error": str}
    """
    try:
        w3 = _get_web3()
        contract = _get_contract(w3)
        account = w3.eth.account.from_key(EVM_PRIVATE_KEY)

        tx = contract.functions.recordResolution(
            claim_id, verdict, reasoning
        ).build_transaction({
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 300_000,
            "gasPrice": w3.eth.gas_price,
        })

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        if receipt.status != 1:
            return {"success": False, "tx_hash": tx_hash.hex(), "error": "Transaction reverted"}

        logger.info(f"Resolution recorded: {claim_id} → {verdict} (TX: {tx_hash.hex()})")
        return {"success": True, "tx_hash": tx_hash.hex(), "error": ""}

    except Exception as e:
        logger.error(f"EVM record_resolution error: {e}")
        return {"success": False, "tx_hash": "", "error": str(e)}


async def get_resolution(claim_id: str) -> dict:
    """
    Read a resolution from the ResolutionRecord contract.

    Returns: {"verdict": bool, "reasoning": str, "timestamp": int}
    """
    try:
        w3 = _get_web3()
        contract = _get_contract(w3)
        result = contract.functions.getResolution(claim_id).call()
        return {
            "verdict": result[0],
            "reasoning": result[1],
            "timestamp": result[2],
        }
    except Exception as e:
        logger.error(f"EVM get_resolution error: {e}")
        return {"verdict": False, "reasoning": "", "timestamp": 0}


# Minimal ABI for PredictionMarket contract
PREDICTION_MARKET_ABI = [
    {
        "inputs": [
            {"name": "claimId", "type": "string"},
            {"name": "claimText", "type": "string"}
        ],
        "name": "createMarket",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "marketId", "type": "uint256"}],
        "name": "verifyMarket",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "marketId", "type": "uint256"}],
        "name": "getMarket",
        "outputs": [
            {
                "components": [
                    {"name": "claimId", "type": "string"},
                    {"name": "claimText", "type": "string"},
                    {"name": "creator", "type": "address"},
                    {"name": "stake", "type": "uint256"},
                    {"name": "status", "type": "uint8"},
                    {"name": "createdAt", "type": "uint256"}
                ],
                "name": "",
                "type": "tuple"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "marketId", "type": "uint256"},
            {"indexed": False, "name": "claimId", "type": "string"},
            {"indexed": False, "name": "creator", "type": "address"},
            {"indexed": False, "name": "stake", "type": "uint256"}
        ],
        "name": "MarketCreated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "marketId", "type": "uint256"}
        ],
        "name": "MarketVerified",
        "type": "event"
    }
]


def _get_prediction_market_contract(w3: Web3):
    """Get the PredictionMarket contract instance."""
    return w3.eth.contract(
        address=Web3.to_checksum_address(PREDICTION_MARKET_ADDRESS),
        abi=PREDICTION_MARKET_ABI,
    )


async def create_prediction_market(claim_id: str, claim_text: str, stake_eth: float = 0.01) -> dict:
    """
    Call PredictionMarket.createMarket() with ETH.
    Returns: {"success": bool, "tx_hash": str, "market_id": int, "error": str}
    """
    try:
        w3 = _get_web3()
        contract = _get_prediction_market_contract(w3)
        account = w3.eth.account.from_key(EVM_PRIVATE_KEY)
        
        stake_wei = w3.to_wei(stake_eth, "ether")
        
        tx = contract.functions.createMarket(
            claim_id, claim_text
        ).build_transaction({
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "value": stake_wei,
            "gas": 300_000,
            "gasPrice": w3.eth.gas_price,
        })
        
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        
        if receipt.status != 1:
            return {"success": False, "tx_hash": tx_hash.hex(), "market_id": 0, "error": "Transaction reverted"}
        
        # Extract marketId from event
        logs = contract.events.MarketCreated().process_receipt(receipt)
        market_id = logs[0].args.marketId if logs else 0
        
        logger.info(f"Prediction Market created: {market_id} (TX: {tx_hash.hex()})")
        return {"success": True, "tx_hash": tx_hash.hex(), "market_id": market_id, "error": ""}
        
    except Exception as e:
        logger.error(f"EVM create_prediction_market error: {e}")
        return {"success": False, "tx_hash": "", "market_id": 0, "error": str(e)}


async def verify_prediction_market(market_id: int) -> dict:
    """
    Call PredictionMarket.verifyMarket().
    Returns: {"success": bool, "tx_hash": str, "error": str}
    """
    try:
        w3 = _get_web3()
        contract = _get_prediction_market_contract(w3)
        account = w3.eth.account.from_key(EVM_PRIVATE_KEY)
        
        tx = contract.functions.verifyMarket(
            market_id
        ).build_transaction({
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 300_000,
            "gasPrice": w3.eth.gas_price,
        })
        
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        
        if receipt.status != 1:
            return {"success": False, "tx_hash": tx_hash.hex(), "error": "Transaction reverted"}
        
        logger.info(f"Market verified on EVM: {market_id} (TX: {tx_hash.hex()})")
        return {"success": True, "tx_hash": tx_hash.hex(), "error": ""}
        
    except Exception as e:
        logger.error(f"EVM verify_prediction_market error: {e}")
        return {"success": False, "tx_hash": "", "error": str(e)}


if __name__ == "__main__":
    import asyncio

    async def main():
        print("Recording test resolution...")
        result = await record_resolution("test_claim", True, "Test from Python")
        print(f"Record result: {result}")

        if result["success"]:
            print("Reading back resolution...")
            resolution = await get_resolution("test_claim")
            print(f"Resolution: {resolution}")

    asyncio.run(main())
