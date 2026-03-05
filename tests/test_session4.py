# tests/test_session4.py — Session 4: Pipeline Integration + CLI
import pytest
import asyncio
import os
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

# Force test DB
os.environ["DB_URL"] = "sqlite+aiosqlite:///test_session4.db"

from db.database import Database
from pipeline.entity_registry import EntityRegistry
from pipeline.orchestrator import (
    process_url,
    PipelineResult,
    _raw_entity_to_entity_data,
    _raw_claim_to_claim_data,
    _conflict_edges_to_edge_data,
)
from pipeline.schemas import (
    AnalysisResult,
    RawEntityData,
    RawClaimData,
    OmissionData,
    ConflictEdge,
    TokenUsage,
)
from interfaces import (
    FetchResult,
    FetchMethod,
    ClassifyResult,
    ArticleType,
    AnalysisDepth,
    EntityData,
    EntityMatch,
    ClaimData,
    ClaimType,
    EdgeData,
    EdgeType,
    EntityTier,
)


# ═══════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════

@pytest.fixture
async def db():
    _db = Database(url="sqlite+aiosqlite:///test_session4.db")
    await _db.init()
    yield _db
    await _db.close()
    if os.path.exists("test_session4.db"):
        os.remove("test_session4.db")


@pytest.fixture
async def registry(db):
    return EntityRegistry(db)


# ═══════════════════════════════════════════
# Mock data factories
# ═══════════════════════════════════════════

def make_fetch_result(url="https://example.com/news/1", title="測試文章標題"):
    return FetchResult(
        url=url,
        title=title,
        text="國民黨與民進黨就國防預算案展開激烈攻防。國民黨立委批評政府預算過高，民進黨則強調國防安全的重要性。" * 5,
        word_count=500,
        char_count=1200,
        fetch_method=FetchMethod.JINA,
        fetched_at=datetime.now(timezone.utc),
        language="zh",
    )


def make_classify_result():
    return ClassifyResult(
        article_type=ArticleType.POLITICAL_CONTROVERSY,
        analysis_depth=AnalysisDepth.DEEP,
        has_quotes=True,
        has_opinion_markers=True,
        has_named_sources=True,
        word_count=500,
        confidence=0.95,
    )


def make_analysis_result():
    return AnalysisResult(
        article_type="political_controversy",
        entities=[
            RawEntityData(
                canonical_id="kmt",
                label="國民黨",
                tier=EntityTier.ORGANIZATION,
                aliases=["KMT", "藍營"],
                country="TW",
                domain="politics",
            ),
            RawEntityData(
                canonical_id="dpp",
                label="民進黨",
                tier=EntityTier.ORGANIZATION,
                aliases=["DPP", "綠營"],
                country="TW",
                domain="politics",
            ),
        ],
        claims=[
            RawClaimData(
                text="國民黨封殺國防預算案",
                type=ClaimType.FACTUAL,
                verifiable=True,
                debatable=True,
                potential_market=True,
                source_entities=["kmt"],
            ),
            RawClaimData(
                text="民進黨強調國防安全",
                type=ClaimType.OPINION,
                verifiable=False,
                debatable=True,
                potential_market=False,
                source_entities=["dpp"],
            ),
        ],
        omissions=[
            OmissionData(
                description="缺少民眾黨的立場",
                perspective="民眾黨",
                importance=0.7,
            ),
        ],
        conflict_graph=[
            ConflictEdge(
                source_claim_idx=0,
                target_claim_idx=1,
                edge_type=EdgeType.CONTRADICTS,
                description="藍綠對國防預算的對立立場",
            ),
        ],
        raw_response='{"article_type": "political_controversy"}',
        model="gpt-4o-mini",
        token_usage=TokenUsage(
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        ),
        cost=0.00045,
    )


# ═══════════════════════════════════════════
# Phase A: Pipeline Orchestrator Tests
# ═══════════════════════════════════════════

class TestConverters:
    """Test helper conversion functions."""

    def test_raw_entity_to_entity_data(self):
        raw = RawEntityData(
            canonical_id="tsmc",
            label="台積電",
            tier=EntityTier.ORGANIZATION,
            aliases=["TSMC", "2330"],
            country="TW",
            domain="semiconductor",
        )
        result = _raw_entity_to_entity_data(raw)
        assert isinstance(result, EntityData)
        assert result.canonical_id == "tsmc"
        assert result.label == "台積電"
        assert result.tier == EntityTier.ORGANIZATION
        assert "TSMC" in result.aliases

    def test_raw_claim_to_claim_data(self):
        raw = RawClaimData(
            text="測試主張",
            type=ClaimType.FACTUAL,
            verifiable=True,
            debatable=False,
            potential_market=True,
            source_entities=["kmt"],
        )
        result = _raw_claim_to_claim_data(raw, "https://example.com")
        assert isinstance(result, ClaimData)
        assert result.text == "測試主張"
        assert result.claim_type == ClaimType.FACTUAL
        assert result.source_article_url == "https://example.com"
        assert result.entity_ids == ["kmt"]

    def test_conflict_edges_to_edge_data(self):
        analysis = make_analysis_result()
        edges = _conflict_edges_to_edge_data(analysis)
        assert len(edges) == 1
        assert edges[0].edge_type == EdgeType.CONTRADICTS
        assert edges[0].source_id == "claim_0"
        assert edges[0].target_id == "claim_1"

    def test_conflict_edges_out_of_bounds_skipped(self):
        analysis = make_analysis_result()
        # Add an edge with out-of-bounds index
        analysis.conflict_graph.append(
            ConflictEdge(
                source_claim_idx=99,
                target_claim_idx=0,
                edge_type=EdgeType.SUPPORTS,
                description="bad edge",
            )
        )
        edges = _conflict_edges_to_edge_data(analysis)
        assert len(edges) == 1  # only the valid edge


class TestProcessUrl:
    """Test process_url end-to-end with mocked externals."""

    @pytest.mark.asyncio
    @patch("pipeline.orchestrator.analyze_article")
    @patch("pipeline.orchestrator.classify_article")
    @patch("pipeline.orchestrator.fetch_article")
    async def test_process_url_full_pipeline(
        self, mock_fetch, mock_classify, mock_analyze, db, registry
    ):
        """process_url should chain all stages and return PipelineResult."""
        mock_fetch.return_value = make_fetch_result()
        mock_classify.return_value = make_classify_result()
        mock_analyze.return_value = make_analysis_result()

        result = await process_url(
            url="https://example.com/news/1",
            db=db,
            registry=registry,
        )

        assert isinstance(result, PipelineResult)
        assert result.url == "https://example.com/news/1"
        assert result.title == "測試文章標題"
        assert result.article_type == "political_controversy"
        assert result.analysis_depth == "deep"

        # Verify pipeline stages were called
        mock_fetch.assert_called_once_with("https://example.com/news/1")
        mock_classify.assert_called_once()
        mock_analyze.assert_called_once()

    @pytest.mark.asyncio
    @patch("pipeline.orchestrator.analyze_article")
    @patch("pipeline.orchestrator.classify_article")
    @patch("pipeline.orchestrator.fetch_article")
    async def test_entities_registered(
        self, mock_fetch, mock_classify, mock_analyze, db, registry
    ):
        """process_url should register all entities via find_or_create."""
        mock_fetch.return_value = make_fetch_result()
        mock_classify.return_value = make_classify_result()
        mock_analyze.return_value = make_analysis_result()

        result = await process_url(
            url="https://example.com/news/2",
            db=db,
            registry=registry,
        )

        assert len(result.entities) == 2
        canonical_ids = {e.canonical_id for e in result.entities}
        assert "kmt" in canonical_ids
        assert "dpp" in canonical_ids

        # Verify entities are in DB
        kmt = await registry.get("kmt")
        assert kmt.label == "國民黨"
        dpp = await registry.get("dpp")
        assert dpp.label == "民進黨"

    @pytest.mark.asyncio
    @patch("pipeline.orchestrator.analyze_article")
    @patch("pipeline.orchestrator.classify_article")
    @patch("pipeline.orchestrator.fetch_article")
    async def test_claims_saved(
        self, mock_fetch, mock_classify, mock_analyze, db, registry
    ):
        """process_url should convert and save all claims."""
        mock_fetch.return_value = make_fetch_result()
        mock_classify.return_value = make_classify_result()
        mock_analyze.return_value = make_analysis_result()

        result = await process_url(
            url="https://example.com/news/3",
            db=db,
            registry=registry,
        )

        assert len(result.claims) == 2
        assert result.claims[0].text == "國民黨封殺國防預算案"
        assert result.claims[0].claim_type == ClaimType.FACTUAL
        assert result.claims[1].text == "民進黨強調國防安全"
        assert result.claims[1].claim_type == ClaimType.OPINION

    @pytest.mark.asyncio
    @patch("pipeline.orchestrator.analyze_article")
    @patch("pipeline.orchestrator.classify_article")
    @patch("pipeline.orchestrator.fetch_article")
    async def test_edges_saved(
        self, mock_fetch, mock_classify, mock_analyze, db, registry
    ):
        """process_url should convert conflict_graph to edges."""
        mock_fetch.return_value = make_fetch_result()
        mock_classify.return_value = make_classify_result()
        mock_analyze.return_value = make_analysis_result()

        result = await process_url(
            url="https://example.com/news/4",
            db=db,
            registry=registry,
        )

        assert len(result.edges) == 1
        assert result.edges[0].edge_type == EdgeType.CONTRADICTS

    @pytest.mark.asyncio
    @patch("pipeline.orchestrator.analyze_article")
    @patch("pipeline.orchestrator.classify_article")
    @patch("pipeline.orchestrator.fetch_article")
    async def test_token_usage_and_cost(
        self, mock_fetch, mock_classify, mock_analyze, db, registry
    ):
        """process_url should include token usage and cost."""
        mock_fetch.return_value = make_fetch_result()
        mock_classify.return_value = make_classify_result()
        mock_analyze.return_value = make_analysis_result()

        result = await process_url(
            url="https://example.com/news/5",
            db=db,
            registry=registry,
        )

        assert result.token_usage["total_tokens"] == 1500
        assert result.cost == pytest.approx(0.00045)

    @pytest.mark.asyncio
    @patch("pipeline.orchestrator.analyze_article")
    @patch("pipeline.orchestrator.classify_article")
    @patch("pipeline.orchestrator.fetch_article")
    async def test_entity_dedup_on_second_url(
        self, mock_fetch, mock_classify, mock_analyze, db, registry
    ):
        """Processing two URLs with overlapping entities should dedup."""
        mock_fetch.return_value = make_fetch_result()
        mock_classify.return_value = make_classify_result()
        mock_analyze.return_value = make_analysis_result()

        await process_url(url="https://example.com/news/6a", db=db, registry=registry)

        # Second URL with same entities
        mock_fetch.return_value = make_fetch_result(url="https://example.com/news/6b", title="第二篇")
        result2 = await process_url(url="https://example.com/news/6b", db=db, registry=registry)

        # Entities should be found as existing, not created again
        for match in result2.entities:
            assert match.match_type in ("exact_id", "alias", "fuzzy")

    @pytest.mark.asyncio
    @patch("pipeline.orchestrator.analyze_article")
    @patch("pipeline.orchestrator.classify_article")
    @patch("pipeline.orchestrator.fetch_article")
    async def test_empty_analysis_result(
        self, mock_fetch, mock_classify, mock_analyze, db, registry
    ):
        """process_url should handle analysis with no entities/claims."""
        mock_fetch.return_value = make_fetch_result()
        mock_classify.return_value = ClassifyResult(
            article_type=ArticleType.DATA_RECAP,
            analysis_depth=AnalysisDepth.SHALLOW,
            has_quotes=False,
            has_opinion_markers=False,
            has_named_sources=False,
            word_count=100,
            confidence=0.95,
        )
        mock_analyze.return_value = AnalysisResult(
            article_type="data_recap",
            entities=[],
            claims=[],
            omissions=[],
            conflict_graph=[],
            raw_response="{}",
            model="gpt-4o-mini",
            token_usage=TokenUsage(),
            cost=0.0,
        )

        result = await process_url(
            url="https://example.com/news/7",
            db=db,
            registry=registry,
        )

        assert isinstance(result, PipelineResult)
        assert len(result.entities) == 0
        assert len(result.claims) == 0
        assert len(result.edges) == 0


# ═══════════════════════════════════════════
# Phase B: CLI Tests
# ═══════════════════════════════════════════

from cli import build_parser, main, cmd_entities_list


class TestCLIParser:
    """Test argparse configuration."""

    def test_analyze_command(self):
        parser = build_parser()
        args = parser.parse_args(["analyze", "https://example.com/news"])
        assert args.command == "analyze"
        assert args.url == "https://example.com/news"

    def test_batch_command(self):
        parser = build_parser()
        args = parser.parse_args(["batch", "urls.txt"])
        assert args.command == "batch"
        assert args.file == "urls.txt"

    def test_entities_list_command(self):
        parser = build_parser()
        args = parser.parse_args(["entities", "list"])
        assert args.command == "entities"
        assert args.entities_command == "list"

    def test_entities_list_with_tier(self):
        parser = build_parser()
        args = parser.parse_args(["entities", "list", "--tier", "person"])
        assert args.command == "entities"
        assert args.entities_command == "list"
        assert args.tier == "person"

    def test_verbose_flag(self):
        parser = build_parser()
        args = parser.parse_args(["-v", "analyze", "https://example.com"])
        assert args.verbose is True

    def test_no_command_shows_help(self):
        """main() with no command should exit with code 1."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 1


class TestCLIAnalyze:
    """Test CLI analyze command with mocked pipeline."""

    @pytest.mark.asyncio
    @patch("cli.process_url")
    @patch("cli._init_services")
    async def test_cmd_analyze_calls_process_url(self, mock_init, mock_process):
        """cmd_analyze should call process_url and print result."""
        mock_db = AsyncMock()
        mock_registry = MagicMock()
        mock_init.return_value = (mock_db, mock_registry)

        mock_process.return_value = PipelineResult(
            url="https://example.com/test",
            title="Test Article",
            article_type="commentary",
            analysis_depth="full",
            entities=[],
            claims=[],
            edges=[],
            token_usage={"total_tokens": 100},
            cost=0.001,
        )

        from cli import cmd_analyze
        await cmd_analyze("https://example.com/test")

        mock_process.assert_called_once()
        mock_db.close.assert_called_once()


class TestCLIBatch:
    """Test CLI batch command."""

    @pytest.mark.asyncio
    async def test_cmd_batch_file_not_found(self):
        """batch with nonexistent file should exit."""
        from cli import cmd_batch
        with pytest.raises(SystemExit):
            await cmd_batch("/nonexistent/urls.txt")

    @pytest.mark.asyncio
    @patch("cli.process_url")
    @patch("cli._init_services")
    async def test_cmd_batch_processes_urls(self, mock_init, mock_process, tmp_path):
        """batch should process each URL in the file."""
        mock_db = AsyncMock()
        mock_registry = MagicMock()
        mock_init.return_value = (mock_db, mock_registry)

        mock_process.return_value = PipelineResult(
            url="https://example.com",
            title="Test",
            article_type="commentary",
            analysis_depth="full",
            entities=[],
            claims=[],
            edges=[],
            token_usage={"total_tokens": 100},
            cost=0.001,
        )

        url_file = tmp_path / "urls.txt"
        url_file.write_text("https://example.com/1\nhttps://example.com/2\n# comment\n\n")

        from cli import cmd_batch
        await cmd_batch(str(url_file))

        assert mock_process.call_count == 2
        mock_db.close.assert_called_once()


class TestCLIEntities:
    """Test CLI entities list command."""

    @pytest.mark.asyncio
    async def test_cmd_entities_list_empty(self, db, registry, capsys):
        """entities list on empty DB should print 'No entities found'."""
        with patch("cli._init_services", return_value=(db, registry)):
            await cmd_entities_list()

        captured = capsys.readouterr()
        assert "No entities found" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_entities_list_with_data(self, db, registry, capsys):
        """entities list should print table of entities."""
        await registry.find_or_create(EntityData(
            canonical_id="tsmc", label="台積電",
            tier=EntityTier.ORGANIZATION, tier_level=2.5,
            aliases=["TSMC"],
        ))

        with patch("cli._init_services", return_value=(db, registry)):
            await cmd_entities_list()

        captured = capsys.readouterr()
        assert "tsmc" in captured.out
        assert "台積電" in captured.out
        assert "Total: 1" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_entities_list_invalid_tier(self):
        """entities list with invalid tier should exit."""
        mock_db = AsyncMock()
        mock_registry = MagicMock()
        with patch("cli._init_services", return_value=(mock_db, mock_registry)):
            with pytest.raises(SystemExit):
                await cmd_entities_list(tier="invalid_tier")
