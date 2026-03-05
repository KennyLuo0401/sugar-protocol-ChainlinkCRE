"""Pipeline Orchestrator — chains fetcher → classifier → analyzer → entity_registry → DB."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

from interfaces import (
    ArticleData,
    ClaimData,
    EdgeData,
    EntityData,
    EntityMatch,
)
from pipeline.fetcher import fetch_article
from pipeline.classifier import classify_article
from pipeline.analyzer import analyze_article
from pipeline.schemas import AnalysisResult, RawEntityData, RawClaimData
from pipeline.entity_registry import EntityRegistry
from db.database import Database

logger = logging.getLogger(__name__)

# Callback type: async function receiving (step: str, progress: float, message: str, extra: dict|None)
ProgressCallback = Callable[..., Coroutine[Any, Any, None]]


@dataclass
class PipelineResult:
    """Result of processing a single URL through the full pipeline."""
    url: str
    title: str
    article_type: str
    analysis_depth: str
    entities: list[EntityMatch] = field(default_factory=list)
    claims: list[ClaimData] = field(default_factory=list)
    edges: list[EdgeData] = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)
    cost: float = 0.0


def _raw_entity_to_entity_data(raw: RawEntityData) -> EntityData:
    """Convert LLM output entity to canonical EntityData."""
    return EntityData(
        canonical_id=raw.canonical_id,
        label=raw.label,
        tier=raw.tier,
        aliases=raw.aliases,
        belongs_to=raw.belongs_to,
        country=raw.country,
        domain=raw.domain,
    )


def _raw_claim_to_claim_data(raw: RawClaimData, source_url: str) -> ClaimData:
    """Convert LLM output claim to canonical ClaimData."""
    return ClaimData(
        text=raw.text,
        claim_type=raw.type,
        verifiable=raw.verifiable,
        debatable=raw.debatable,
        potential_market=raw.potential_market,
        source_article_url=source_url,
        entity_ids=raw.source_entities,
    )


def _conflict_edges_to_edge_data(analysis: AnalysisResult) -> list[EdgeData]:
    """Convert conflict graph edges (claim indices) to EdgeData."""
    edges = []
    for edge in analysis.conflict_graph:
        if edge.source_claim_idx < len(analysis.claims) and edge.target_claim_idx < len(analysis.claims):
            edges.append(EdgeData(
                source_id=f"claim_{edge.source_claim_idx}",
                target_id=f"claim_{edge.target_claim_idx}",
                edge_type=edge.edge_type,
                note=edge.description,
            ))
    return edges


async def process_url(
    url: str,
    db: Database,
    registry: EntityRegistry,
    on_progress: Optional[ProgressCallback] = None,
) -> PipelineResult:
    """
    Process a single URL through the full pipeline.

    Steps:
    1. Fetch article text (Jina Reader / BS4 fallback)
    2. Classify article type (regex heuristics)
    3. Analyze with LLM (Framework C prompt)
    4. Register entities (find_or_create with dedup)
    5. Save article, claims, edges to DB
    6. Return PipelineResult
    """
    async def _notify(step: str, progress: float, message: str):
        if on_progress:
            await on_progress(step, progress, message)

    # 1. Fetch
    await _notify("fetching", 0.1, "Fetching article...")
    logger.info("Fetching: %s", url)
    fetch_result = await fetch_article(url)
    logger.info("Fetched: %s (%d chars)", fetch_result.title, fetch_result.char_count)

    # 2. Classify
    await _notify("classifying", 0.2, "Classifying article type...")
    classify_result = classify_article(fetch_result.text)
    logger.info(
        "Classified: %s → %s",
        classify_result.article_type.value,
        classify_result.analysis_depth.value,
    )

    # 3. Analyze with LLM
    await _notify("analyzing", 0.4, "Analyzing with LLM...")
    analysis = await analyze_article(
        text=fetch_result.text,
        depth=classify_result.analysis_depth,
        language=fetch_result.language,
    )
    logger.info(
        "Analyzed: %d entities, %d claims, $%.4f",
        len(analysis.entities),
        len(analysis.claims),
        analysis.cost,
    )

    # 4. Register entities
    await _notify("resolving", 0.7, "Resolving entities...")
    entity_matches = []
    for raw_entity in analysis.entities:
        entity_data = _raw_entity_to_entity_data(raw_entity)
        match = await registry.find_or_create(entity_data)
        entity_matches.append(match)
        logger.info(
            "Entity: %s → %s (%s)",
            raw_entity.label, match.canonical_id, match.match_type,
        )

    # 5. Convert claims and edges
    claims = [_raw_claim_to_claim_data(raw, url) for raw in analysis.claims]
    edges = _conflict_edges_to_edge_data(analysis)

    # 6. Save to DB
    await _notify("saving", 0.9, "Saving to database...")
    article_data = ArticleData(
        url=url,
        title=fetch_result.title,
        article_type=classify_result.article_type,
        analysis_depth=classify_result.analysis_depth,
        language=fetch_result.language,
        raw_analysis_json=analysis.raw_response,
    )
    await registry.save_article(article_data)

    for claim in claims:
        await registry.save_claim(claim)

    for edge in edges:
        await registry.save_edge(edge)

    logger.info("Saved to DB: %s", url)

    return PipelineResult(
        url=url,
        title=fetch_result.title,
        article_type=classify_result.article_type.value,
        analysis_depth=classify_result.analysis_depth.value,
        entities=entity_matches,
        claims=claims,
        edges=edges,
        token_usage={
            "prompt_tokens": analysis.token_usage.prompt_tokens,
            "completion_tokens": analysis.token_usage.completion_tokens,
            "total_tokens": analysis.token_usage.total_tokens,
        },
        cost=analysis.cost,
    )
