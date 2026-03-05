"""Entity Registry — deduplication, fuzzy matching, and CRUD for entities."""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from thefuzz import fuzz

import config
from db.models import EntityModel, ClaimModel, ArticleModel, EdgeModel
from db.database import get_session
from interfaces import (
    EntityData,
    ClaimData,
    EdgeData,
    ArticleData,
    EntityMatch,
    EntityNotFoundError,
    DuplicateEntityError,
    EntityTier,
)


def _model_to_entity_data(m: EntityModel) -> EntityData:
    """Convert an ORM model to an EntityData pydantic model."""
    return EntityData(
        canonical_id=m.canonical_id,
        label=m.label,
        tier=EntityTier(m.tier),
        tier_level=m.tier_level,
        aliases=m.aliases if isinstance(m.aliases, list) else [],
        belongs_to=m.belongs_to,
        country=m.country,
        domain=m.domain,
        topic=m.topic,
    )


async def find_or_create(
    session: AsyncSession, entity: EntityData
) -> EntityMatch:
    """
    Find an existing entity or create a new one.

    Matching strategy (in order):
    1. Exact canonical_id match
    2. Alias fuzzy match (thefuzz ratio >= FUZZY_MATCH_THRESHOLD)
    3. Create new entity
    """
    # 1. Exact canonical_id match
    result = await session.execute(
        select(EntityModel).where(EntityModel.canonical_id == entity.canonical_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return EntityMatch(
            canonical_id=existing.canonical_id,
            label=existing.label,
            tier=EntityTier(existing.tier),
            match_type="exact_id",
            confidence=1.0,
        )

    # 2. Fuzzy match against all existing entities' labels and aliases
    threshold = config.FUZZY_MATCH_THRESHOLD
    all_entities = await session.execute(select(EntityModel))
    best_match: Optional[EntityModel] = None
    best_score = 0
    match_type = "fuzzy"

    for row in all_entities.scalars():
        # Check label
        score = fuzz.ratio(entity.label.lower(), row.label.lower())
        if score > best_score:
            best_score = score
            best_match = row
            match_type = "fuzzy"

        # Check aliases
        aliases = row.aliases if isinstance(row.aliases, list) else []
        for alias in aliases:
            score = fuzz.ratio(entity.label.lower(), alias.lower())
            if score > best_score:
                best_score = score
                best_match = row
                match_type = "alias"

        # Also check incoming entity aliases against existing label
        for incoming_alias in entity.aliases:
            score = fuzz.ratio(incoming_alias.lower(), row.label.lower())
            if score > best_score:
                best_score = score
                best_match = row
                match_type = "alias"

    if best_match is not None and best_score >= threshold:
        return EntityMatch(
            canonical_id=best_match.canonical_id,
            label=best_match.label,
            tier=EntityTier(best_match.tier),
            match_type=match_type,
            confidence=best_score / 100.0,
        )

    # 3. Create new entity
    new_entity = EntityModel(
        canonical_id=entity.canonical_id,
        label=entity.label,
        tier=entity.tier.value,
        tier_level=entity.tier_level,
        aliases=entity.aliases,
        belongs_to=entity.belongs_to,
        country=entity.country,
        domain=entity.domain,
        topic=entity.topic,
    )
    session.add(new_entity)
    await session.flush()

    return EntityMatch(
        canonical_id=entity.canonical_id,
        label=entity.label,
        tier=entity.tier,
        match_type="created",
        confidence=1.0,
    )


async def merge_entities(
    session: AsyncSession, keep_id: str, remove_id: str
) -> EntityData:
    """
    Merge remove_id into keep_id: combine aliases, update edge references, delete old.

    Returns the updated EntityData for keep_id.
    Raises EntityNotFoundError if either entity doesn't exist.
    """
    keep_result = await session.execute(
        select(EntityModel).where(EntityModel.canonical_id == keep_id)
    )
    keep_entity = keep_result.scalar_one_or_none()
    if keep_entity is None:
        raise EntityNotFoundError(keep_id)

    remove_result = await session.execute(
        select(EntityModel).where(EntityModel.canonical_id == remove_id)
    )
    remove_entity = remove_result.scalar_one_or_none()
    if remove_entity is None:
        raise EntityNotFoundError(remove_id)

    # Merge aliases
    existing_aliases = set(keep_entity.aliases if isinstance(keep_entity.aliases, list) else [])
    existing_aliases.add(remove_entity.label)
    remove_aliases = remove_entity.aliases if isinstance(remove_entity.aliases, list) else []
    existing_aliases.update(remove_aliases)
    existing_aliases.discard(keep_entity.label)
    keep_entity.aliases = sorted(existing_aliases)

    # Update edge references: source_id
    await session.execute(
        update(EdgeModel)
        .where(EdgeModel.source_id == remove_id)
        .values(source_id=keep_id)
    )
    # Update edge references: target_id
    await session.execute(
        update(EdgeModel)
        .where(EdgeModel.target_id == remove_id)
        .values(target_id=keep_id)
    )

    # Delete the removed entity
    await session.execute(
        delete(EntityModel).where(EntityModel.canonical_id == remove_id)
    )

    await session.flush()
    return _model_to_entity_data(keep_entity)


async def get_related(
    session: AsyncSession, canonical_id: str, depth: int = 1
) -> list[EntityData]:
    """
    Get entities related to canonical_id within `depth` hops via edges.

    Returns a list of EntityData (excluding the queried entity itself).
    Raises EntityNotFoundError if the entity doesn't exist.
    """
    # Verify entity exists
    result = await session.execute(
        select(EntityModel).where(EntityModel.canonical_id == canonical_id)
    )
    if result.scalar_one_or_none() is None:
        raise EntityNotFoundError(canonical_id)

    visited: set[str] = {canonical_id}
    frontier: set[str] = {canonical_id}

    for _ in range(depth):
        if not frontier:
            break
        # Find all edges touching current frontier
        edges_out = await session.execute(
            select(EdgeModel.target_id).where(EdgeModel.source_id.in_(frontier))
        )
        edges_in = await session.execute(
            select(EdgeModel.source_id).where(EdgeModel.target_id.in_(frontier))
        )
        neighbors = set()
        for (nid,) in edges_out:
            if nid not in visited:
                neighbors.add(nid)
        for (nid,) in edges_in:
            if nid not in visited:
                neighbors.add(nid)

        visited.update(neighbors)
        frontier = neighbors

    # Exclude the original entity
    related_ids = visited - {canonical_id}
    if not related_ids:
        return []

    result = await session.execute(
        select(EntityModel).where(EntityModel.canonical_id.in_(related_ids))
    )
    return [_model_to_entity_data(m) for m in result.scalars()]


async def seed_entities(session: AsyncSession, seed_path: str | None = None) -> int:
    """
    Import entities from a JSON seed file. Skips duplicates.

    Returns the number of entities created.
    """
    path = seed_path or config.ENTITY_SEED_PATH
    with open(path, "r", encoding="utf-8") as f:
        seed_data = json.load(f)

    count = 0
    for entry in seed_data:
        entity = EntityData(**entry)
        result = await session.execute(
            select(EntityModel).where(EntityModel.canonical_id == entity.canonical_id)
        )
        if result.scalar_one_or_none() is not None:
            continue
        model = EntityModel(
            canonical_id=entity.canonical_id,
            label=entity.label,
            tier=entity.tier.value,
            tier_level=entity.tier_level,
            aliases=entity.aliases,
            belongs_to=entity.belongs_to,
            country=entity.country,
            domain=entity.domain,
            topic=entity.topic,
        )
        session.add(model)
        count += 1

    await session.flush()
    return count


async def save_analysis(
    session: AsyncSession,
    article: ArticleData,
    entities: list[EntityData],
    claims: list[ClaimData],
    edges: list[EdgeData],
) -> None:
    """Save a complete analysis result: article, entities, claims, and edges."""
    # Save article
    article_model = ArticleModel(
        url=article.url,
        title=article.title,
        article_type=article.article_type.value,
        analysis_depth=article.analysis_depth.value,
        language=article.language,
        raw_analysis_json=article.raw_analysis_json,
    )
    session.add(article_model)

    # Upsert entities
    for entity in entities:
        result = await session.execute(
            select(EntityModel).where(EntityModel.canonical_id == entity.canonical_id)
        )
        if result.scalar_one_or_none() is None:
            model = EntityModel(
                canonical_id=entity.canonical_id,
                label=entity.label,
                tier=entity.tier.value,
                tier_level=entity.tier_level,
                aliases=entity.aliases,
                belongs_to=entity.belongs_to,
                country=entity.country,
                domain=entity.domain,
                topic=entity.topic,
            )
            session.add(model)

    # Save claims
    for claim in claims:
        claim_model = ClaimModel(
            text=claim.text,
            claim_type=claim.claim_type.value,
            verifiable=claim.verifiable,
            debatable=claim.debatable,
            potential_market=claim.potential_market,
            source_article_url=claim.source_article_url,
            entity_ids=claim.entity_ids,
        )
        session.add(claim_model)

    # Save edges
    for edge in edges:
        edge_model = EdgeModel(
            source_id=edge.source_id,
            target_id=edge.target_id,
            edge_type=edge.edge_type.value,
            note=edge.note,
        )
        session.add(edge_model)

    await session.flush()

class EntityRegistry:
    """Class wrapper for test compatibility."""

    def __init__(self, db) -> None:
        self._db = db

    async def find_or_create(self, entity: EntityData) -> EntityMatch:
        async with get_session() as session:
            return await find_or_create(session, entity)

    async def save_article(self, article: ArticleData) -> str:
        import uuid
        async with get_session() as session:
            raw_json = article.raw_analysis_json
            if isinstance(raw_json, dict):
                raw_json = json.dumps(raw_json, ensure_ascii=False)
            article_model = ArticleModel(
                url=article.url,
                title=article.title,
                article_type=article.article_type.value,
                analysis_depth=article.analysis_depth.value,
                language=article.language,
                raw_analysis_json=raw_json,
            )
            session.add(article_model)
            await session.flush()
            return str(article_model.id)

    async def save_claim(self, claim: ClaimData) -> str:
        import uuid
        async with get_session() as session:
            obj = ClaimModel(
                text=claim.text,
                claim_type=claim.claim_type.value,
                verifiable=claim.verifiable,
                verify_how=getattr(claim, "verify_how", None),
                source_article_url=claim.source_article_url,
                entity_ids=claim.entity_ids or [],
            )
            session.add(obj)
            await session.flush()
            return str(obj.id)

    async def save_edge(self, edge: EdgeData) -> None:
        async with get_session() as session:
            obj = EdgeModel(
                source_id=edge.source_id,
                target_id=edge.target_id,
                edge_type=edge.edge_type.value,
                note=getattr(edge, "note", None),
            )
            session.add(obj)

    async def seed(self, entities: list[EntityData]) -> int:
        count = 0
        async with get_session() as session:
            for entity in entities:
                result = await session.execute(
                    select(EntityModel).where(EntityModel.canonical_id == entity.canonical_id)
                )
                if result.scalar_one_or_none() is not None:
                    continue
                model = EntityModel(
                    canonical_id=entity.canonical_id,
                    label=entity.label,
                    tier=entity.tier.value,
                    tier_level=entity.tier_level,
                    aliases=entity.aliases,
                    belongs_to=entity.belongs_to,
                    country=entity.country,
                    domain=entity.domain,
                    topic=entity.topic,
                )
                session.add(model)
                count += 1
            await session.flush()
        return count

    async def get_related(self, canonical_id: str, depth: int = 1):
        async with get_session() as session:
            return await get_related(session, canonical_id, depth)

    async def get(self, canonical_id: str) -> EntityData:
        async with get_session() as session:
            result = await session.execute(
                select(EntityModel).where(EntityModel.canonical_id == canonical_id)
            )
            obj = result.scalar_one_or_none()
            if obj is None:
                raise EntityNotFoundError(f"Entity not found: {canonical_id}")
            return _model_to_entity_data(obj)

    async def search(self, query: str) -> list[EntityData]:
        async with get_session() as session:
            result = await session.execute(select(EntityModel))
            all_entities = result.scalars().all()
            matches = []
            for obj in all_entities:
                if (query.lower() in obj.label.lower() or
                    query.lower() in obj.canonical_id.lower() or
                    any(query.lower() in a.lower() for a in (obj.aliases or []))):
                    matches.append(_model_to_entity_data(obj))
            return matches

    async def list_all(self, tier=None) -> list[EntityData]:
        async with get_session() as session:
            stmt = select(EntityModel)
            if tier is not None:
                stmt = stmt.where(EntityModel.tier == tier.value)
            result = await session.execute(stmt)
            return [_model_to_entity_data(obj) for obj in result.scalars().all()]

    async def add_alias(self, canonical_id: str, alias: str) -> EntityData:
        async with get_session() as session:
            result = await session.execute(
                select(EntityModel).where(EntityModel.canonical_id == canonical_id)
            )
            obj = result.scalar_one_or_none()
            if obj is None:
                raise EntityNotFoundError(f"Entity not found: {canonical_id}")
            aliases = list(obj.aliases or [])
            if alias not in aliases:
                aliases.append(alias)
            obj.aliases = aliases
            await session.flush()
            return _model_to_entity_data(obj)

    async def merge(self, canonical_id_a: str, canonical_id_b: str) -> EntityData:
        async with get_session() as session:
            return await merge_entities(session, canonical_id_a, canonical_id_b)
