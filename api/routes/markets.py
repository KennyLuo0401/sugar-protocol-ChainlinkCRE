import time
import logging
import os

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from datetime import datetime

import openai

from api.sui_bridge import create_market as sui_create_market, resolve_market as sui_resolve_market
from api.evm_bridge import record_resolution, get_resolution, verify_prediction_market
from api.routes.resolve import MOCK_RESOLUTIONS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["markets"])

# 黑客松 Mock Data — 與 resolve.py MOCK_RESOLUTIONS 對應
MOCK_MARKETS: Dict[str, Dict[str, Any]] = {
    "market_tsmc_n2": {
        "id": "market_tsmc_n2",
        "claim_id": "claim_tsmc_n2",
        "question": "台積電 2 奈米製程將於 2025 年開始量產",
        "for_pool": 15000000000,
        "against_pool": 5000000000,
        "for_percentage": 75,
        "deadline": 1740873600000,
        "resolved": False,
        "outcome": None,
        "resolution": None,
        "total_stakers": 12,
        "created_at": "2026-02-10T00:00:00Z"
    },
    "market_btc_100k": {
        "id": "market_btc_100k",
        "claim_id": "claim_btc_100k",
        "question": "比特幣價格將在 2026 年 2 月底前突破 100,000 美元",
        "for_pool": 8400000000,
        "against_pool": 11600000000,
        "for_percentage": 42,
        "deadline": 1740787200000,
        "resolved": False,
        "outcome": None,
        "resolution": None,
        "total_stakers": 45,
        "created_at": "2026-02-12T00:00:00Z"
    },
    "market_ko_verdict": {
        "id": "market_ko_verdict",
        "claim_id": "claim_ko_verdict",
        "question": "柯文哲京華城案將於今日釋出最終判決結果",
        "for_pool": 3600000000,
        "against_pool": 16400000000,
        "for_percentage": 18,
        "deadline": 1740000000000,
        "resolved": True,
        "outcome": False,
        "total_stakers": 89,
        "created_at": "2026-02-15T00:00:00Z",
        "resolution": {
            "verdict": False,
            "reasoning": "根據最新司法進度，本案目前仍處於偵查或二審審理階段，並無今日釋出最終判決之公告。",
            "resolved_at": "2026-02-20T12:00:00Z",
            "chainlink_verified": True
        }
    },
    "market_nv_tsmc": {
        "id": "market_nv_tsmc",
        "claim_id": "claim_nv_tsmc",
        "question": "NVIDIA 計劃於下週完成對台積電的惡意併購",
        "for_pool": 1000000000,
        "against_pool": 19000000000,
        "for_percentage": 5,
        "deadline": 1740614400000,
        "resolved": True,
        "outcome": False,
        "total_stakers": 230,
        "created_at": "2026-02-18T00:00:00Z",
        "resolution": {
            "verdict": False,
            "reasoning": "台積電與 NVIDIA 均未發布相關重大訊息，且法律限制與產業結構使得此類併購案在下週完成的可能性為零。",
            "resolved_at": "2026-02-20T12:00:00Z",
            "chainlink_verified": True
        }
    }
}

@router.get("/markets")
async def list_markets():
    """List all truth markets."""
    markets = list(MOCK_MARKETS.values())
    return {"markets": markets, "total": len(markets)}

@router.get("/markets/{market_id}")
async def get_market(market_id: str):
    """Get a specific market with stake history."""
    if market_id not in MOCK_MARKETS:
        raise HTTPException(status_code=404, detail=f"Market not found: {market_id}")
    
    market = MOCK_MARKETS[market_id].copy()
    # 加上 stakes_history mock
    market["stakes_history"] = [
        {"staker": "0xabc...123", "amount": 2000000000, "is_for": True, "timestamp": "2026-02-11T08:30:00Z"},
        {"staker": "0xdef...456", "amount": 1000000000, "is_for": False, "timestamp": "2026-02-12T14:00:00Z"},
        {"staker": "0x789...ghi", "amount": 500000000, "is_for": True, "timestamp": "2026-02-13T09:15:00Z"}
    ]
    return market


@router.post("/markets/create")
async def create_market_endpoint(request: dict):
    """
    Create a new Truth Market on Sui Testnet.

    Body: { "claim_text": str, "deadline_days": int (default 7) }
    """
    claim_text = request.get("claim_text")
    if not claim_text:
        raise HTTPException(status_code=400, detail="claim_text is required")

    deadline_days = request.get("deadline_days", 7)
    deadline_ms = int((time.time() + deadline_days * 86400) * 1000)

    result = await sui_create_market(claim_text, deadline_ms)

    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"Sui transaction failed: {result['error']}",
        )

    return {
        "status": "created",
        "market_id": result["market_id"],
        "tx_digest": result["tx_digest"],
        "claim_id": result["claim_id"],
        "claim_text": claim_text,
        "deadline_ms": deadline_ms,
    }


@router.post("/markets/{market_id}/resolve")
async def resolve_market_endpoint(market_id: str, request: dict):
    """
    Resolve a Truth Market on Sui Testnet.

    Body: { "outcome": bool, "reasoning": str (optional) }
    """
    outcome = request.get("outcome")
    if outcome is None:
        raise HTTPException(status_code=400, detail="outcome (bool) is required")

    reasoning = request.get("reasoning", "")

    result = await sui_resolve_market(market_id, bool(outcome))

    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"Sui resolve failed: {result['error']}",
        )

    return {
        "status": "resolved",
        "market_id": market_id,
        "outcome": outcome,
        "reasoning": reasoning,
        "tx_digest": result["tx_digest"],
    }


async def _llm_verdict(claim_text: str, nlp_summary: str) -> dict:
    """Call OpenAI to produce a verdict for a claim. Returns {verdict, confidence, reasoning}."""
    client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    prompt = (
        "You are a fact-checking judge. Given a claim and its NLP analysis summary, "
        "determine whether the claim is TRUE or FALSE.\n\n"
        f"Claim: {claim_text}\n\n"
        f"NLP Summary: {nlp_summary}\n\n"
        "Respond in JSON with exactly these fields:\n"
        '{"verdict": true/false, "confidence": 0.0-1.0, "reasoning": "one paragraph explanation"}'
    )
    resp = await client.chat.completions.create(
        model=os.environ.get("DEFAULT_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
        timeout=30,
    )
    import json
    return json.loads(resp.choices[0].message.content)


@router.post("/markets/{market_id}/auto-resolve")
async def auto_resolve_market(market_id: str, request: dict):
    """
    One-click full resolution pipeline:
    1. Retrieve claim data from resolve.py
    2. LLM verdict via OpenAI
    3. Write ResolutionRecord to EVM (Tenderly)
    4. Resolve TruthMarket on Sui Testnet
    """
    claim_id = request.get("claim_id")
    if not claim_id:
        raise HTTPException(status_code=400, detail="claim_id is required")

    # Step 1: Get claim data
    claim_data = MOCK_RESOLUTIONS.get(claim_id)
    if not claim_data:
        raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

    claim_text = claim_data["claim_text"]
    nlp_summary = claim_data["nlp_summary"]

    # Step 2: LLM verdict
    try:
        llm_result = await _llm_verdict(claim_text, nlp_summary)
        verdict = bool(llm_result.get("verdict", False))
        confidence = float(llm_result.get("confidence", 0.0))
        reasoning = llm_result.get("reasoning", "")
    except Exception as e:
        logger.error(f"LLM verdict failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM verdict failed: {e}")

    # Step 3: Write to EVM
    evm_result = await record_resolution(claim_id, verdict, reasoning)
    if not evm_result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"EVM write failed: {evm_result['error']}",
        )

    # Step 4: Resolve on Sui
    sui_result = await sui_resolve_market(market_id, verdict)
    if not sui_result["success"]:
        # EVM succeeded but Sui failed — report both
        return {
            "status": "partial",
            "verdict": verdict,
            "confidence": confidence,
            "reasoning": reasoning,
            "evm_tx_hash": evm_result["tx_hash"],
            "sui_error": sui_result["error"],
        }

    return {
        "status": "resolved",
        "verdict": verdict,
        "confidence": confidence,
        "reasoning": reasoning,
        "evm_tx_hash": evm_result["tx_hash"],
        "sui_tx_digest": sui_result["tx_digest"],
        "market_id": market_id,
        "claim_id": claim_id,
    }


@router.post("/markets/{market_id}/cre-verify")
async def cre_verify_market(market_id: str):
    """
    模擬 CRE 掃描 MarketCreated event 並驗證市場（Demo 用）。

    流程：
    1. 從 MOCK_MARKETS 查 market 資料（找不到回 404）
    2. 呼叫 evm_bridge.verify_prediction_market(int(market_id))
    3. 回傳 { "status": "verified", "market_id": str, "tx_hash": str }
    4. 失敗回 500
    """
    if market_id not in MOCK_MARKETS:
        # 註：雖然 ID 是數字，但 MOCK_MARKETS 用字串作為 key，例如 "market_tsmc_n2"
        # 為了 Demo 彈性，這裡僅做紀錄，實際合約呼叫需轉 int
        logger.warning(f"Market ID {market_id} not in MOCK_MARKETS, proceeding with EVM call.")

    try:
        # EVM 合約中的 marketId 是 uint256
        evm_market_id = int(market_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="market_id must be an integer for EVM call")

    result = await verify_prediction_market(evm_market_id)
    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"EVM verify_market failed: {result['error']}",
        )

    return {
        "status": "verified",
        "market_id": market_id,
        "tx_hash": result["tx_hash"]
    }
