# tests/test_session3.py
import pytest
import asyncio
import os

# Force test DB
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_session3.db"

from db.database import Database
from pipeline.entity_registry import EntityRegistry
from interfaces import (
    EntityData, EntityTier, EntityMatch,
    ClaimData, ClaimType,
    ArticleData, EdgeData, EdgeType,
    EntityNotFoundError, DuplicateEntityError,
)


@pytest.fixture
async def db():
    """Create a fresh test database for each test."""
    _db = Database(url="sqlite+aiosqlite:///test_session3.db")
    await _db.init()
    yield _db
    await _db.close()
    # Clean up
    if os.path.exists("test_session3.db"):
        os.remove("test_session3.db")


@pytest.fixture
async def registry(db):
    return EntityRegistry(db)


class TestDatabase:

    @pytest.mark.asyncio
    async def test_init_creates_tables(self, db):
        """init() should create all tables without error."""
        await db.init()  # second call should be idempotent

    @pytest.mark.asyncio
    async def test_session_context_manager(self, db):
        """session() should yield a usable async session."""
        async with db.session() as session:
            assert session is not None


class TestEntityRegistry:

    @pytest.mark.asyncio
    async def test_create_new_entity(self, registry):
        """find_or_create with new entity should create it."""
        data = EntityData(
            canonical_id="tsmc",
            label="台積電 TSMC",
            tier=EntityTier.ORGANIZATION,
            tier_level=2.5,
            aliases=["TSMC", "2330", "台灣半導體"],
            country="TW",
            domain="economy",
            topic="stock",
        )
        match = await registry.find_or_create(data)
        assert isinstance(match, EntityMatch)
        assert match.canonical_id == "tsmc"
        assert match.match_type == "created"

    @pytest.mark.asyncio
    async def test_find_by_canonical_id(self, registry):
        """find_or_create should find existing entity by canonical_id."""
        data = EntityData(
            canonical_id="kmt", label="國民黨", tier=EntityTier.ORGANIZATION,
            tier_level=2.5, aliases=["KMT", "藍營"],
        )
        await registry.find_or_create(data)
        
        # Search again with same canonical_id
        data2 = EntityData(
            canonical_id="kmt", label="國民黨 KMT", tier=EntityTier.ORGANIZATION,
            tier_level=2.5,
        )
        match = await registry.find_or_create(data2)
        assert match.match_type == "exact_id"
        assert match.canonical_id == "kmt"

    @pytest.mark.asyncio
    async def test_find_by_alias(self, registry):
        """find_or_create should find existing entity by alias match."""
        data = EntityData(
            canonical_id="tsmc", label="台積電",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
            aliases=["TSMC", "2330"],
        )
        await registry.find_or_create(data)
        
        # Search with different canonical_id but matching alias
        data2 = EntityData(
            canonical_id="taiwan_semi", label="TSMC",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
            aliases=["TSMC"],
        )
        match = await registry.find_or_create(data2)
        assert match.match_type == "alias"
        assert match.canonical_id == "tsmc"  # returns existing, not new

    @pytest.mark.asyncio
    async def test_get_existing(self, registry):
        """get() should return entity data."""
        data = EntityData(
            canonical_id="dpp", label="民進黨",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
            aliases=["DPP", "綠營"],
        )
        await registry.find_or_create(data)
        
        result = await registry.get("dpp")
        assert result.canonical_id == "dpp"
        assert result.label == "民進黨"
        assert "DPP" in result.aliases

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self, registry):
        """get() should raise EntityNotFoundError."""
        with pytest.raises(EntityNotFoundError):
            await registry.get("nonexistent_entity")

    @pytest.mark.asyncio
    async def test_search_by_label(self, registry):
        """search() should find entities by label substring."""
        await registry.find_or_create(EntityData(
            canonical_id="tsmc", label="台積電 TSMC",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
        ))
        await registry.find_or_create(EntityData(
            canonical_id="kmt", label="國民黨 KMT",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
        ))
        
        results = await registry.search("台積")
        assert len(results) == 1
        assert results[0].canonical_id == "tsmc"

    @pytest.mark.asyncio
    async def test_search_by_alias(self, registry):
        """search() should also match aliases."""
        await registry.find_or_create(EntityData(
            canonical_id="tsmc", label="台積電",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
            aliases=["TSMC", "2330"],
        ))
        
        results = await registry.search("2330")
        assert len(results) >= 1
        assert any(r.canonical_id == "tsmc" for r in results)

    @pytest.mark.asyncio
    async def test_list_all(self, registry):
        """list_all() should return all entities."""
        await registry.find_or_create(EntityData(
            canonical_id="tw", label="台灣",
            tier=EntityTier.COUNTRY, tier_level=0,
        ))
        await registry.find_or_create(EntityData(
            canonical_id="kmt", label="國民黨",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
        ))
        
        all_entities = await registry.list_all()
        assert len(all_entities) == 2

    @pytest.mark.asyncio
    async def test_list_filtered_by_tier(self, registry):
        """list_all(tier=...) should filter."""
        await registry.find_or_create(EntityData(
            canonical_id="tw", label="台灣",
            tier=EntityTier.COUNTRY, tier_level=0,
        ))
        await registry.find_or_create(EntityData(
            canonical_id="kmt", label="國民黨",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
        ))
        
        countries = await registry.list_all(tier=EntityTier.COUNTRY)
        assert len(countries) == 1
        assert countries[0].canonical_id == "tw"

    @pytest.mark.asyncio
    async def test_add_alias(self, registry):
        """add_alias() should add to existing aliases."""
        await registry.find_or_create(EntityData(
            canonical_id="tsmc", label="台積電",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
            aliases=["TSMC"],
        ))
        
        result = await registry.add_alias("tsmc", "台灣半導體")
        assert "台灣半導體" in result.aliases
        assert "TSMC" in result.aliases  # old alias preserved

    @pytest.mark.asyncio
    async def test_merge_entities(self, registry):
        """merge() should combine two entities."""
        await registry.find_or_create(EntityData(
            canonical_id="nvidia", label="輝達 NVIDIA",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
            aliases=["NVIDIA"],
        ))
        await registry.find_or_create(EntityData(
            canonical_id="nvidia_corp", label="NVIDIA Corp",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
            aliases=["NVDA"],
        ))
        
        result = await registry.merge("nvidia", "nvidia_corp")
        assert result.canonical_id == "nvidia"
        assert "NVDA" in result.aliases  # alias from removed entity
        
        # removed entity should be gone
        with pytest.raises(EntityNotFoundError):
            await registry.get("nvidia_corp")

    @pytest.mark.asyncio
    async def test_save_article(self, registry):
        """save_article() should store and return UUID."""
        article = ArticleData(
            url="https://example.com/news/1",
            title="測試文章",
            article_type="commentary",
            analysis_depth="full",
            language="zh",
            raw_analysis_json={"claims": [], "entities": []},
        )
        article_id = await registry.save_article(article)
        assert isinstance(article_id, str)
        assert len(article_id) > 0

    @pytest.mark.asyncio
    async def test_save_claim(self, registry):
        """save_claim() should store and return UUID."""
        # First save an article
        article = ArticleData(
            url="https://example.com/news/2",
            title="測試",
            article_type="commentary",
            analysis_depth="full",
            raw_analysis_json={},
        )
        await registry.save_article(article)
        
        claim = ClaimData(
            text="藍白已十度封殺國防預算",
            claim_type=ClaimType.FACTUAL,
            verifiable=True,
            verify_how="立法院議事錄",
            source_article_url="https://example.com/news/2",
            entity_ids=["kmt", "tpp"],
        )
        claim_id = await registry.save_claim(claim)
        assert isinstance(claim_id, str)
        assert len(claim_id) > 0

    @pytest.mark.asyncio
    async def test_save_edge(self, registry):
        """save_edge() should not raise."""
        edge = EdgeData(
            source_id="kmt",
            target_id="s_block",
            edge_type=EdgeType.DERIVES,
            note="國民黨推動阻擋預算",
        )
        await registry.save_edge(edge)  # should not raise

    @pytest.mark.asyncio
    async def test_seed(self, registry):
        """seed() should bulk insert and return count."""
        entities = [
            EntityData(canonical_id="tw", label="台灣", tier=EntityTier.COUNTRY, tier_level=0),
            EntityData(canonical_id="us", label="美國", tier=EntityTier.COUNTRY, tier_level=0),
            EntityData(canonical_id="jp", label="日本", tier=EntityTier.COUNTRY, tier_level=0),
        ]
        count = await registry.seed(entities)
        assert count == 3
        
        # Seed again — should skip existing
        count2 = await registry.seed(entities)
        assert count2 == 0