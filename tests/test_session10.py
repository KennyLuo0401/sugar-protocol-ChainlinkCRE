import pytest
import os
import asyncio

# Setup env before imports
os.environ["DB_URL"] = "sqlite+aiosqlite:///test_session10.db"

from httpx import AsyncClient, ASGITransport
from api.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    if os.path.exists("test_session10.db"):
        try:
            os.remove("test_session10.db")
        except:
            pass

@pytest.mark.asyncio
async def test_list_markets_200(client):
    """1. GET /api/markets -> 200，回傳 4 筆 markets"""
    response = await client.get("/api/markets")
    assert response.status_code == 200
    data = response.json()
    assert "markets" in data
    assert len(data["markets"]) == 4
    assert data["total"] == 4

@pytest.mark.asyncio
async def test_market_fields(client):
    """2. GET /api/markets -> 每筆 market 有必要欄位"""
    response = await client.get("/api/markets")
    data = response.json()
    required_fields = ["id", "claim_id", "question", "for_pool", "against_pool", "for_percentage", "deadline", "resolved"]
    for market in data["markets"]:
        for field in required_fields:
            assert field in market

@pytest.mark.asyncio
async def test_total_field_correct(client):
    """3. GET /api/markets -> total 欄位正確"""
    response = await client.get("/api/markets")
    data = response.json()
    assert data["total"] == len(data["markets"])

@pytest.mark.asyncio
async def test_get_specific_market_200(client):
    """4. GET /api/markets/market_tsmc_n2 -> 200，回傳正確 market"""
    response = await client.get("/api/markets/market_tsmc_n2")
    assert response.status_code == 200
    market = response.json()
    assert market["id"] == "market_tsmc_n2"
    assert "台積電" in market["question"]

@pytest.mark.asyncio
async def test_market_detail_stakes_history(client):
    """5. GET /api/markets/market_tsmc_n2 -> 包含 stakes_history 陣列"""
    response = await client.get("/api/markets/market_tsmc_n2")
    market = response.json()
    assert "stakes_history" in market
    assert len(market["stakes_history"]) >= 2
    for stake in market["stakes_history"]:
        assert "staker" in stake
        assert "amount" in stake
        assert "is_for" in stake

@pytest.mark.asyncio
async def test_resolved_market_status(client):
    """6. GET /api/markets/market_ko_verdict -> resolved == true, outcome == false"""
    response = await client.get("/api/markets/market_ko_verdict")
    market = response.json()
    assert market["resolved"] is True
    assert market["outcome"] is False

@pytest.mark.asyncio
async def test_market_resolution_chainlink(client):
    """7. GET /api/markets/market_ko_verdict -> 包含 resolution 欄位且 chainlink_verified == true"""
    response = await client.get("/api/markets/market_ko_verdict")
    market = response.json()
    assert "resolution" in market
    assert market["resolution"]["chainlink_verified"] is True
    assert "reasoning" in market["resolution"]

@pytest.mark.asyncio
async def test_market_not_found(client):
    """8. GET /api/markets/nonexistent -> 404"""
    response = await client.get("/api/markets/nonexistent")
    assert response.status_code == 404
    assert "detail" in response.json()

@pytest.mark.asyncio
async def test_percentage_range(client):
    """9. GET /api/markets -> 所有 for_percentage 值在 0-100 之間"""
    response = await client.get("/api/markets")
    data = response.json()
    for market in data["markets"]:
        assert 0 <= market["for_percentage"] <= 100

@pytest.mark.asyncio
async def test_claim_id_prefix(client):
    """10. GET /api/markets -> 所有 claim_id 都以 claim_ 開頭"""
    response = await client.get("/api/markets")
    data = response.json()
    for market in data["markets"]:
        assert market["claim_id"].startswith("claim_")
