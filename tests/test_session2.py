# Sugar Protocol — Session 2 Tests
# LLM analysis engine: schemas, prompts, analyzer
# Run: PYTHONPATH=. pytest tests/test_session2.py -v

import os
import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from interfaces import AnalysisDepth, AnalyzeError, ClaimType, EdgeType, EntityTier
from pipeline.schemas import (
    AnalysisResult, RawEntityData, RawClaimData, OmissionData, ConflictEdge,
    TokenUsage,
)
from pipeline.prompts.framework_c import get_system_prompt
from pipeline.analyzer import analyze_article, _fix_json, _estimate_cost


# ═══════════════════════════════════════════
# SCHEMA TESTS
# ═══════════════════════════════════════════

class TestSchemas:

    def test_entity_data_valid(self):
        entity = RawEntityData(
            canonical_id="tsmc",
            label="台積電",
            tier=EntityTier.ORGANIZATION,
            aliases=["TSMC", "2330"],
            country="TW",
            domain="semiconductor",
        )
        assert entity.canonical_id == "tsmc"
        assert entity.tier == EntityTier.ORGANIZATION

    def test_entity_data_minimal(self):
        entity = RawEntityData(canonical_id="btc", label="Bitcoin", tier=EntityTier.DOMAIN)
        assert entity.aliases == []
        assert entity.belongs_to is None
        assert entity.country is None

    def test_claim_data_defaults(self):
        claim = RawClaimData(text="Test claim")
        assert claim.type == ClaimType.FACTUAL
        assert claim.verifiable is True
        assert claim.debatable is False
        assert claim.potential_market is False
        assert claim.source_entities == []

    def test_claim_types(self):
        for ct in ClaimType:
            claim = RawClaimData(text="x", type=ct)
            assert claim.type == ct

    def test_omission_data(self):
        omission = OmissionData(
            description="Missing opposition view",
            perspective="Opposition party",
            importance=0.8,
        )
        assert omission.importance == 0.8

    def test_omission_importance_bounds(self):
        with pytest.raises(Exception):
            OmissionData(description="x", perspective="y", importance=1.5)

    def test_conflict_edge(self):
        edge = ConflictEdge(
            source_claim_idx=0,
            target_claim_idx=1,
            edge_type=EdgeType.CONTRADICTS,
            description="Opposing views",
        )
        assert edge.edge_type == EdgeType.CONTRADICTS

    def test_analysis_result_full(self):
        result = AnalysisResult(
            article_type="commentary",
            entities=[RawEntityData(canonical_id="a", label="A", tier=EntityTier.PERSON)],
            claims=[RawClaimData(text="claim1")],
            omissions=[OmissionData(description="d", perspective="p", importance=0.5)],
            conflict_graph=[ConflictEdge(source_claim_idx=0, target_claim_idx=0, edge_type=EdgeType.SUPPORTS)],
            raw_response="{}",
            model="gpt-4o-mini",
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            cost=0.001,
        )
        assert len(result.entities) == 1
        assert result.cost == 0.001

    def test_analysis_result_empty(self):
        result = AnalysisResult(article_type="unknown")
        assert result.entities == []
        assert result.claims == []
        assert result.omissions == []
        assert result.conflict_graph == []
        assert result.cost == 0.0


# ═══════════════════════════════════════════
# PROMPT TESTS
# ═══════════════════════════════════════════

class TestPrompts:

    def test_get_system_prompt_all_depths_zh(self):
        for depth in AnalysisDepth:
            prompt = get_system_prompt(depth, "zh")
            assert len(prompt) > 100
            assert "JSON" in prompt or "json" in prompt

    def test_get_system_prompt_all_depths_en(self):
        for depth in AnalysisDepth:
            prompt = get_system_prompt(depth, "en")
            assert len(prompt) > 100
            assert "JSON" in prompt or "json" in prompt

    def test_shallow_prompt_is_shorter(self):
        shallow = get_system_prompt(AnalysisDepth.SHALLOW, "zh")
        deep = get_system_prompt(AnalysisDepth.DEEP, "zh")
        assert len(shallow) < len(deep)

    def test_deep_prompt_mentions_omissions(self):
        prompt = get_system_prompt(AnalysisDepth.DEEP, "zh")
        assert "omissions" in prompt.lower() or "遺漏" in prompt

    def test_shallow_prompt_no_omission_instructions(self):
        """SHALLOW instruction section should not ask for omission analysis."""
        prompt = get_system_prompt(AnalysisDepth.SHALLOW, "zh")
        # The schema template always lists "omissions" as a JSON key,
        # but the instruction text should NOT ask the LLM to analyze omissions.
        instruction_part = prompt.split("你必須以 JSON 格式回覆")[0]
        assert "遺漏" not in instruction_part
        assert "omission" not in instruction_part.lower()

    def test_prompt_contains_example(self):
        prompt = get_system_prompt(AnalysisDepth.STANDARD, "zh")
        assert "canonical_id" in prompt
        assert "claims" in prompt

    def test_english_prompt_language(self):
        prompt = get_system_prompt(AnalysisDepth.FULL, "en")
        assert "You are" in prompt or "Extract" in prompt


# ═══════════════════════════════════════════
# JSON FIX TESTS
# ═══════════════════════════════════════════

class TestJsonFix:

    def test_fix_markdown_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        assert json.loads(_fix_json(raw)) == {"key": "value"}

    def test_fix_trailing_comma_object(self):
        raw = '{"a": 1, "b": 2,}'
        assert json.loads(_fix_json(raw)) == {"a": 1, "b": 2}

    def test_fix_trailing_comma_array(self):
        raw = '{"arr": [1, 2, 3,]}'
        assert json.loads(_fix_json(raw)) == {"arr": [1, 2, 3]}

    def test_fix_comments(self):
        raw = '{"key": "value" // comment\n}'
        assert json.loads(_fix_json(raw)) == {"key": "value"}

    def test_valid_json_unchanged(self):
        raw = '{"key": "value"}'
        assert _fix_json(raw) == raw

    def test_fix_combined(self):
        raw = '```json\n{"a": 1, // comment\n"b": [2,],}\n```'
        result = json.loads(_fix_json(raw))
        assert result == {"a": 1, "b": [2]}


# ═══════════════════════════════════════════
# COST ESTIMATION TESTS
# ═══════════════════════════════════════════

class TestCostEstimation:

    def test_gpt4o_mini_cost(self):
        cost = _estimate_cost("gpt-4o-mini", 1000, 500)
        # 1000 * 0.15/1M + 500 * 0.60/1M = 0.00015 + 0.0003 = 0.00045
        assert abs(cost - 0.00045) < 1e-6

    def test_unknown_model_fallback(self):
        cost = _estimate_cost("some-unknown-model", 1000, 500)
        # Falls back to gpt-4o-mini pricing
        assert cost > 0


# ═══════════════════════════════════════════
# ANALYZER TESTS (MOCKED)
# ═══════════════════════════════════════════

# Sample LLM response for mocking
_MOCK_RESPONSE_JSON = json.dumps({
    "article_type": "commentary",
    "entities": [
        {"canonical_id": "tsmc", "label": "台積電", "tier": "organization",
         "aliases": ["TSMC"], "country": "TW", "domain": "semiconductor"},
    ],
    "claims": [
        {"text": "台積電營收創新高", "type": "factual", "verifiable": True,
         "debatable": False, "potential_market": False, "source_entities": ["tsmc"]},
        {"text": "AI需求將持續推動半導體成長", "type": "prediction", "verifiable": False,
         "debatable": True, "potential_market": True, "source_entities": []},
    ],
    "omissions": [],
    "conflict_graph": [],
})


def _make_mock_response(content: str = _MOCK_RESPONSE_JSON, prompt_tokens: int = 500, completion_tokens: int = 200):
    """Create a mock OpenAI ChatCompletion response."""
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = prompt_tokens
    mock_usage.completion_tokens = completion_tokens
    mock_usage.total_tokens = prompt_tokens + completion_tokens

    mock_message = MagicMock()
    mock_message.content = content

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    return mock_response


class TestAnalyzer:

    @pytest.mark.asyncio
    async def test_analyze_returns_result(self):
        """Basic: returns AnalysisResult with correct data."""
        mock_response = _make_mock_response()

        with patch("pipeline.analyzer.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat = MagicMock()
            instance.chat.completions = MagicMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("pipeline.analyzer.config") as mock_config:
                mock_config.OPENAI_API_KEY = "sk-test"
                mock_config.DEFAULT_MODEL = "gpt-4o-mini"
                mock_config.LLM_MAX_RETRIES = 3
                mock_config.LLM_TIMEOUT = 30

                result = await analyze_article(
                    text="台積電今日宣布營收創新高",
                    depth=AnalysisDepth.FULL,
                )

        assert isinstance(result, AnalysisResult)
        assert len(result.entities) == 1
        assert result.entities[0].canonical_id == "tsmc"
        assert len(result.claims) == 2
        assert result.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_analyze_token_tracking(self):
        """Token usage and cost should be tracked."""
        mock_response = _make_mock_response(prompt_tokens=1000, completion_tokens=500)

        with patch("pipeline.analyzer.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat = MagicMock()
            instance.chat.completions = MagicMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("pipeline.analyzer.config") as mock_config:
                mock_config.OPENAI_API_KEY = "sk-test"
                mock_config.DEFAULT_MODEL = "gpt-4o-mini"
                mock_config.LLM_MAX_RETRIES = 3
                mock_config.LLM_TIMEOUT = 30

                result = await analyze_article(
                    text="Some article text",
                    depth=AnalysisDepth.STANDARD,
                )

        assert result.token_usage.prompt_tokens == 1000
        assert result.token_usage.completion_tokens == 500
        assert result.token_usage.total_tokens == 1500
        assert result.cost > 0

    @pytest.mark.asyncio
    async def test_analyze_empty_text_raises(self):
        """Empty text should raise AnalyzeError."""
        with pytest.raises(AnalyzeError) as exc_info:
            await analyze_article(text="", depth=AnalysisDepth.SHALLOW)
        assert "Empty" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_analyze_no_api_key_raises(self):
        """Missing API key should raise AnalyzeError."""
        with patch("pipeline.analyzer.config") as mock_config:
            mock_config.OPENAI_API_KEY = ""
            mock_config.DEFAULT_MODEL = "gpt-4o-mini"

            with pytest.raises(AnalyzeError) as exc_info:
                await analyze_article(text="Some text", depth=AnalysisDepth.SHALLOW)
            assert "API" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_analyze_json_with_markdown_fence(self):
        """LLM response wrapped in markdown fence should still parse."""
        fenced = f"```json\n{_MOCK_RESPONSE_JSON}\n```"
        mock_response = _make_mock_response(content=fenced)

        with patch("pipeline.analyzer.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat = MagicMock()
            instance.chat.completions = MagicMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("pipeline.analyzer.config") as mock_config:
                mock_config.OPENAI_API_KEY = "sk-test"
                mock_config.DEFAULT_MODEL = "gpt-4o-mini"
                mock_config.LLM_MAX_RETRIES = 3
                mock_config.LLM_TIMEOUT = 30

                result = await analyze_article(
                    text="Some text",
                    depth=AnalysisDepth.FULL,
                )

        assert len(result.entities) == 1

    @pytest.mark.asyncio
    async def test_analyze_retry_on_api_error(self):
        """Should retry on API timeout and eventually succeed."""
        from openai import APITimeoutError
        import httpx

        mock_response = _make_mock_response()
        mock_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")

        with patch("pipeline.analyzer.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat = MagicMock()
            instance.chat.completions = MagicMock()
            # First call times out, second succeeds
            instance.chat.completions.create = AsyncMock(
                side_effect=[
                    APITimeoutError(request=mock_request),
                    mock_response,
                ]
            )

            with patch("pipeline.analyzer.config") as mock_config:
                mock_config.OPENAI_API_KEY = "sk-test"
                mock_config.DEFAULT_MODEL = "gpt-4o-mini"
                mock_config.LLM_MAX_RETRIES = 3
                mock_config.LLM_TIMEOUT = 30

                # Patch sleep to avoid waiting
                with patch("pipeline.analyzer.asyncio.sleep", new_callable=AsyncMock):
                    result = await analyze_article(
                        text="Some text",
                        depth=AnalysisDepth.STANDARD,
                    )

        assert isinstance(result, AnalysisResult)
        assert instance.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_analyze_all_retries_fail(self):
        """Should raise AnalyzeError after all retries exhausted."""
        from openai import APITimeoutError
        import httpx

        mock_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")

        with patch("pipeline.analyzer.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat = MagicMock()
            instance.chat.completions = MagicMock()
            instance.chat.completions.create = AsyncMock(
                side_effect=APITimeoutError(request=mock_request),
            )

            with patch("pipeline.analyzer.config") as mock_config:
                mock_config.OPENAI_API_KEY = "sk-test"
                mock_config.DEFAULT_MODEL = "gpt-4o-mini"
                mock_config.LLM_MAX_RETRIES = 3
                mock_config.LLM_TIMEOUT = 30

                with patch("pipeline.analyzer.asyncio.sleep", new_callable=AsyncMock):
                    with pytest.raises(AnalyzeError) as exc_info:
                        await analyze_article(text="Some text", depth=AnalysisDepth.FULL)

        assert "retries failed" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_analyze_depth_affects_prompt(self):
        """Different depths should produce different system prompts."""
        mock_response = _make_mock_response()
        captured_messages = []

        async def capture_create(**kwargs):
            captured_messages.append(kwargs["messages"])
            return mock_response

        with patch("pipeline.analyzer.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat = MagicMock()
            instance.chat.completions = MagicMock()
            instance.chat.completions.create = AsyncMock(side_effect=capture_create)

            with patch("pipeline.analyzer.config") as mock_config:
                mock_config.OPENAI_API_KEY = "sk-test"
                mock_config.DEFAULT_MODEL = "gpt-4o-mini"
                mock_config.LLM_MAX_RETRIES = 3
                mock_config.LLM_TIMEOUT = 30

                await analyze_article(text="Text", depth=AnalysisDepth.SHALLOW)
                await analyze_article(text="Text", depth=AnalysisDepth.DEEP)

        # System prompts should differ between SHALLOW and DEEP
        shallow_system = captured_messages[0][0]["content"]
        deep_system = captured_messages[1][0]["content"]
        assert shallow_system != deep_system
        assert len(deep_system) > len(shallow_system)

    @pytest.mark.asyncio
    async def test_analyze_custom_model(self):
        """Should use custom model when specified."""
        mock_response = _make_mock_response()

        with patch("pipeline.analyzer.AsyncOpenAI") as MockClient:
            instance = MockClient.return_value
            instance.chat = MagicMock()
            instance.chat.completions = MagicMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("pipeline.analyzer.config") as mock_config:
                mock_config.OPENAI_API_KEY = "sk-test"
                mock_config.DEFAULT_MODEL = "gpt-4o-mini"
                mock_config.LLM_MAX_RETRIES = 3
                mock_config.LLM_TIMEOUT = 30

                result = await analyze_article(
                    text="Text", depth=AnalysisDepth.FULL, model="gpt-4o",
                )

        assert result.model == "gpt-4o"
        call_kwargs = instance.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o"


# ═══════════════════════════════════════════
# END-TO-END TEST (requires API key)
# ═══════════════════════════════════════════

@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping e2e test",
)
class TestAnalyzerE2E:

    @pytest.mark.asyncio
    async def test_e2e_analyze_chinese_article(self):
        """End-to-end: analyze a short Chinese article with real API."""
        text = """
        台積電今日宣布，2024年第一季營收達到5926億元新台幣，較去年同期成長16.5%。
        法人分析師認為，主要受惠於AI晶片需求強勁，特別是來自輝達的訂單。
        不過也有分析師警告，地緣政治風險可能影響未來展望。
        台積電董事長劉德音表示「對AI需求的長期趨勢保持樂觀」。
        """
        result = await analyze_article(
            text=text,
            depth=AnalysisDepth.FULL,
            language="zh",
        )
        assert isinstance(result, AnalysisResult)
        assert len(result.entities) > 0
        assert len(result.claims) > 0
        assert result.token_usage.total_tokens > 0
        assert result.cost > 0
        assert result.model == "gpt-4o-mini"
