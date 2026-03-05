from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any

router = APIRouter(prefix="/api", tags=["resolve"])

# Hackathon Mock Data
# Topics: TSMC N2, Bitcoin, Ko Wen-je Case
MOCK_RESOLUTIONS: Dict[str, Dict[str, Any]] = {
    "claim_tsmc_n2": {
        "claim_id": "claim_tsmc_n2",
        "claim_text": "台積電 2 奈米製程將於 2025 年開始量產",
        "claim_type": "factual",
        "verifiable": True,
        "source_urls": ["https://news.tsmc.com/chinese/items/202404/test1.html"],
        "related_entities": ["台積電", "2奈米", "量產"],
        "nlp_summary": "根據台積電法說會與官方新聞稿，2 奈米 (N2) 技術研發進展順利，預計將於 2025 年如期進入量產階段。此聲稱與多個權威財經媒體報導一致。",
        "expected_verdict": True
    },
    "claim_btc_100k": {
        "claim_id": "claim_btc_100k",
        "claim_text": "比特幣價格將在 2026 年 2 月底前突破 100,000 美元",
        "claim_type": "prediction",
        "verifiable": True,
        "source_urls": ["https://www.coindesk.com/market-analysis"],
        "related_entities": ["比特幣", "加密貨幣", "10萬美元"],
        "nlp_summary": "目前市場情緒樂觀，但受限於宏觀經濟波動與監管政策，BTC 仍在 90k 附近震盪。此為預測性主張，尚無定論。",
        "expected_verdict": None # Pending
    },
    "claim_ko_verdict": {
        "claim_id": "claim_ko_verdict",
        "claim_text": "柯文哲京華城案將於今日釋出最終判決結果",
        "claim_type": "factual",
        "verifiable": True,
        "source_urls": ["https://news.ltn.com.tw/topic/ko-case"],
        "related_entities": ["柯文哲", "京華城案", "判決"],
        "nlp_summary": "目前案件仍在司法偵查階段，北院尚未排定宣判日期。今日並無判決公告，此聲稱屬於預測性或誤導性資訊。",
        "expected_verdict": None # Pending
    },
    "claim_nv_tsmc": {
        "claim_id": "claim_nv_tsmc",
        "claim_text": "NVIDIA 計劃於下週完成對台積電的惡意併購",
        "claim_type": "factual",
        "verifiable": True,
        "source_urls": ["https://www.reuters.com/technology"],
        "related_entities": ["NVIDIA", "台積電", "併購"],
        "nlp_summary": "無任何官方公告或監管文件顯示此併購案。考慮到台積電在台灣的戰略地位與反壟斷法規，此聲稱極大機率為虛假資訊。",
        "expected_verdict": False
    }
}

@router.get("/resolve")
async def get_resolve_data(claim_id: str = Query(..., description="The Sui Object ID of the claim")):
    """
    Endpoint for Chainlink CRE to fetch NLP context for a claim.
    Returns mocked data for Hackathon simulation.
    """
    if claim_id not in MOCK_RESOLUTIONS:
        # Fallback to a default response if ID is not in mock (useful for dynamic testing)
        return {
            "claim_id": claim_id,
            "claim_text": f"Dynamic testing for claim {claim_id}",
            "claim_type": "factual",
            "verifiable": True,
            "source_urls": [],
            "related_entities": [],
            "nlp_summary": "未能在黑客松測試數據庫中找到此 ID，進入預設處理流程。"
        }
    
    return MOCK_RESOLUTIONS[claim_id]
