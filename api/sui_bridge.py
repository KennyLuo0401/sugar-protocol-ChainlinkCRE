"""Sui CLI wrapper for Sugar Protocol — calls sui client to interact with Testnet contracts."""

import subprocess
import json
import hashlib
import os
import logging

logger = logging.getLogger(__name__)

SUI_PACKAGE_ID = os.environ.get(
    "SUI_PACKAGE_ID",
    "0xdf6f05bc4424ffc1ec027a4badee36d842b83112aa8b29ff50a598d02964e6a7",
)
SUI_ADMIN_CAP_ID = os.environ.get(
    "SUI_ADMIN_CAP_ID",
    "0xfcc110837b33bd928eb1aa8dfe6ed90a56728753132e9f1f1362c95e02b63ecd",
)
GAS_BUDGET = int(os.environ.get("SUI_GAS_BUDGET", "10000000"))


def generate_claim_id(claim_text: str) -> str:
    """Generate a deterministic 32-byte hex ID from claim text."""
    h = hashlib.sha256(claim_text.encode("utf-8")).hexdigest()
    return f"0x{h}"


async def create_market(claim_text: str, deadline_ms: int) -> dict:
    """
    Call sui client call to create a TruthMarket on Sui Testnet.

    Returns: { "success": bool, "tx_digest": str, "market_id": str, "claim_id": str, "error": str }
    """
    claim_id = generate_claim_id(claim_text)

    cmd = [
        "sui", "client", "call",
        "--package", SUI_PACKAGE_ID,
        "--module", "market",
        "--function", "create_market",
        "--args",
        SUI_ADMIN_CAP_ID,
        claim_id,
        claim_text,
        str(deadline_ms),
        "--gas-budget", str(GAS_BUDGET),
        "--json",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            logger.error(f"Sui CLI error: {result.stderr}")
            return {"success": False, "error": result.stderr.strip()}

        tx_data = json.loads(result.stdout)
        tx_digest = tx_data.get("digest", "")

        # Find the newly created TruthMarket object ID from objectChanges
        market_id = ""
        for change in tx_data.get("objectChanges", []):
            if change.get("type") == "created" and "TruthMarket" in change.get("objectType", ""):
                market_id = change.get("objectId", "")
                break

        logger.info(f"Market created: {market_id} (TX: {tx_digest})")
        return {
            "success": True,
            "tx_digest": tx_digest,
            "market_id": market_id,
            "claim_id": claim_id,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Sui CLI timeout (30s)"}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Failed to parse Sui CLI output: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def resolve_market(market_object_id: str, outcome: bool) -> dict:
    """
    Call sui client call to resolve a TruthMarket on Sui Testnet.

    Args:
        market_object_id: The Sui Object ID of the TruthMarket
        outcome: True if claim is verified true, False otherwise

    Returns: { "success": bool, "tx_digest": str, "market_id": str, "outcome": bool, "error": str }
    """
    cmd = [
        "sui", "client", "call",
        "--package", SUI_PACKAGE_ID,
        "--module", "market",
        "--function", "resolve",
        "--args",
        SUI_ADMIN_CAP_ID,
        market_object_id,
        str(outcome).lower(),
        "--gas-budget", str(GAS_BUDGET),
        "--json",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            logger.error(f"Sui resolve error: {result.stderr}")
            return {"success": False, "error": result.stderr.strip()}

        tx_data = json.loads(result.stdout)
        tx_digest = tx_data.get("digest", "")

        logger.info(f"Market resolved: {market_object_id} → {outcome} (TX: {tx_digest})")
        return {
            "success": True,
            "tx_digest": tx_digest,
            "market_id": market_object_id,
            "outcome": outcome,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Sui CLI timeout (30s)"}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Failed to parse Sui CLI output: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
