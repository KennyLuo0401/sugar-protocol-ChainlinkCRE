import pytest
import os
import datetime
from unittest.mock import patch, AsyncMock

# 設定測試 DB
os.environ["DB_URL"] = "sqlite+aiosqlite:///test_session5.db"

from httpx import AsyncClient, ASGITransport
from api.main import app
from db.database import Database
from pipeline.entity_registry import EntityRegistry
from pipeline.orchestrator import PipelineResult
from interfaces import EntityMatch, ClaimData, EdgeData, EntityData, EntityTier, ClaimType, FetchError, AnalyzeError

# 讓 pytest 知道要用 asyncio
pytestmark = pytest.mark.asyncio

@pytest.fixture
async def client():
    # 手動初始化 State (模擬 Lifespan Startup)
    # 因為 ASGITransport 預設不觸發 lifespan 事件，我們需手動掛載 db 和 registry
    db = Database()
    await db.init()
    app.state.db = db
    app.state.registry = EntityRegistry(db)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    
    # 手動執行 Shutdown
    await db.close()
    
    # cleanup
    if os.path.exists("test_session5.db"):
        os.remove("test_session5.db")

# --- Articles Tests ---

@patch("api.routes.articles.process_url")
async def test_analyze_success(mock_process, client):
    # Mock return value
    mock_process.return_value = PipelineResult(
        url="https://example.com/test",
        title="Test Article",
        article_type="commentary",
        analysis_depth="full",
        entities=[
            EntityMatch(canonical_id="tsmc", label="台積電", tier=EntityTier.ORGANIZATION, match_type="exact", confidence=1.0)
        ],
        claims=[
            ClaimData(text="TSMC is growing", claim_type=ClaimType.FACTUAL, verifiable=True, debatable=False, potential_market=False, entity_ids=["tsmc"], source_article_url=None, source_in_article=None, verify_how=None)
        ],
        edges=[],
        token_usage={"total_tokens": 100},
        cost=0.001,
    )
    
    resp = await client.post("/api/analyze", json={"url": "https://example.com/test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["url"] == "https://example.com/test"
    assert len(data["entities"]) == 1
    assert data["entities"][0]["canonical_id"] == "tsmc"
    assert len(data["claims"]) == 1

async def test_analyze_missing_url(client):
    resp = await client.post("/api/analyze", json={})
    assert resp.status_code == 422

@patch("api.routes.articles.process_url")
async def test_analyze_fetch_error(mock_process, client):
    # FetchError 補足參數 (url, reason)
    mock_process.side_effect = FetchError("https://example.com/fail", "Timeout")
    resp = await client.post("/api/analyze", json={"url": "https://example.com/fail"})
    assert resp.status_code == 400
    assert "Timeout" in resp.json()["detail"]

async def test_get_articles_empty(client):
    resp = await client.get("/api/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["articles"] == []
    assert data["total"] == 0

async def test_get_articles_with_data(client):
    # 手動插入假資料
    from db.models import ArticleModel
    db = app.state.db
    async with db.session() as session:
        article = ArticleModel(
            url="http://test.com", title="Test", article_type="news", 
            analysis_depth="deep", language="en", analyzed_at=datetime.datetime.now()
        )
        session.add(article)

    resp = await client.get("/api/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["articles"]) == 1
    assert data["articles"][0]["url"] == "http://test.com"

# --- Entities Tests ---

@patch("pipeline.entity_registry.EntityRegistry.list_all")
async def test_entities_list_empty(mock_list, client):
    mock_list.return_value = []
    resp = await client.get("/api/entities")
    assert resp.status_code == 200
    assert resp.json()["entities"] == []

@patch("pipeline.entity_registry.EntityRegistry.list_all")
async def test_entities_list_data(mock_list, client):
    mock_list.return_value = [
        EntityData(canonical_id="e1", label="E1", tier=EntityTier.PERSON, tier_level=1.0, aliases=[], belongs_to=None, country=None, domain=None, topic=None)
    ]
    resp = await client.get("/api/entities")
    assert resp.status_code == 200
    assert len(resp.json()["entities"]) == 1

@patch("pipeline.entity_registry.EntityRegistry.list_all")
async def test_entities_filter_tier(mock_list, client):
    mock_list.return_value = []
    resp = await client.get("/api/entities?tier=person")
    assert resp.status_code == 200
    mock_list.assert_called_with(tier=EntityTier.PERSON)

@patch("pipeline.entity_registry.EntityRegistry.get")
async def test_entity_get_existing(mock_get, client):
    mock_get.return_value = EntityData(canonical_id="kmt", label="KMT", tier=EntityTier.ORGANIZATION, tier_level=2.0, aliases=[], belongs_to=None, country="TW", domain=None, topic=None)
    resp = await client.get("/api/entities/kmt")
    assert resp.status_code == 200
    assert resp.json()["canonical_id"] == "kmt"

@patch("pipeline.entity_registry.EntityRegistry.get")
async def test_entity_get_not_found(mock_get, client):
    from interfaces import EntityNotFoundError
    mock_get.side_effect = EntityNotFoundError("not found")
    resp = await client.get("/api/entities/missing")
    assert resp.status_code == 404

# --- Graph Tests ---

async def test_graph_empty(client):
    resp = await client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == []
    assert data["edges"] == []

async def test_graph_with_data(client):
    from db.models import EntityModel, ClaimModel, EdgeModel
    db = app.state.db
    async with db.session() as session:
        e = EntityModel(canonical_id="g1", label="G1", tier="person", tier_level=1, aliases=[], belongs_to=None, country=None, domain=None, topic="defense")
        c = ClaimModel(id=101, text="Claim 101", claim_type="factual", verifiable=True, debatable=False, potential_market=False, entity_ids=["g1"])
        edge = EdgeModel(id=1, source_id="g1", target_id="claim_101", edge_type="contains", note="")
        session.add_all([e, c, edge])
        await session.commit()

    resp = await client.get("/api/graph?topic=defense")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) >= 2
    # 檢查是否含有 entity node
    assert any(n["id"] == "g1" and n["type"] == "entity" for n in data["nodes"])
    # 檢查是否含有 claim node
    assert any(n["id"] == "claim_101" and n["type"] == "claim" for n in data["nodes"])

# --- Search Tests ---

@patch("pipeline.entity_registry.EntityRegistry.search")
async def test_search_success(mock_search, client):
    mock_search.return_value = [
        EntityData(canonical_id="tsmc", label="TSMC", tier=EntityTier.ORGANIZATION, tier_level=1.0, aliases=[], belongs_to=None, country=None, domain=None, topic=None)
    ]
    
    # 寫入一個 claim 供搜尋
    from db.models import ClaimModel
    db = app.state.db
    async with db.session() as session:
        c = ClaimModel(id=202, text="TSMC revenue is high", claim_type="factual", verifiable=True, debatable=False, potential_market=False, entity_ids=[])
        session.add(c)
        await session.commit()

    resp = await client.get("/api/search?q=TSMC")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "TSMC"
    assert len(data["entities"]) == 1
    assert len(data["claims"]) == 1
    assert data["claims"][0]["text"] == "TSMC revenue is high"

async def test_search_missing_q(client):
    resp = await client.get("/api/search")
    # FastAPI 對於缺少的必填 Query 參數預設回傳 422 Unprocessable Entity
    assert resp.status_code == 422

# --- CORS Test ---

async def test_cors_headers(client):
    origin = "http://localhost:3000"
    resp = await client.options("/api/analyze", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST"
    })
    
    assert resp.status_code == 200
    # 當 allow_credentials=True 時，Response Header 會回傳具體的 Origin 而不是 *
    assert resp.headers["access-control-allow-origin"] == origin