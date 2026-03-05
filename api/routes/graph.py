from fastapi import APIRouter, Depends
from typing import Optional
from sqlalchemy import select, func
import json as json_module

from api.deps import get_db
from db.database import Database
from db.models import EntityModel, ClaimModel, EdgeModel, ArticleModel

router = APIRouter()

@router.get("/graph")
async def get_graph_data(
    topic: Optional[str] = None,
    db: Database = Depends(get_db)
):
    async with db.session() as session:
        # 1. 查 Entities (若有 topic 則過濾)
        entity_stmt = select(EntityModel)
        if topic:
            entity_stmt = entity_stmt.where(EntityModel.topic == topic)
        
        entity_result = await session.execute(entity_stmt)
        entities = entity_result.scalars().all()

        # 2. 查 Claims
        claim_stmt = select(ClaimModel)
        claim_result = await session.execute(claim_stmt)
        claims = claim_result.scalars().all()

        # 3. 查 Edges
        edge_stmt = select(EdgeModel)
        edge_result = await session.execute(edge_stmt)
        db_edges = edge_result.scalars().all()

        # 4. 查 Article count
        article_count_result = await session.execute(select(func.count()).select_from(ArticleModel))
        article_count = article_count_result.scalar() or 0

        # 5. 組合 Nodes
        nodes = []
        node_ids = set()
        
        # Entity Nodes
        for e in entities:
            nodes.append({
                "id": e.canonical_id,
                "label": e.label,
                "type": "entity",
                "tier": e.tier
            })
            node_ids.add(e.canonical_id)
            
        # Claim Nodes (with claim_type)
        for c in claims:
            claim_node_id = f"claim_{c.id}"
            nodes.append({
                "id": claim_node_id,
                "label": c.text,
                "type": "claim",
                "claim_type": c.claim_type or "factual"
            })
            node_ids.add(claim_node_id)

        # 6. 組合 Edges
        edges = []
        seen_edges = set()
        
        # DB Edges (claim↔claim)
        for edge in db_edges:
            key = (edge.source_id, edge.target_id, edge.edge_type)
            if key not in seen_edges:
                edges.append({
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.edge_type
                })
                seen_edges.add(key)

        # Entity hierarchy edges (belongs_to → contains)
        for e in entities:
            if e.belongs_to and e.belongs_to in node_ids:
                key = (e.belongs_to, e.canonical_id, "contains")
                if key not in seen_edges:
                    edges.append({
                        "source": e.belongs_to,
                        "target": e.canonical_id,
                        "type": "contains"
                    })
                    seen_edges.add(key)

        # Entity↔Claim edges (from claims.entity_ids)
        for c in claims:
            claim_node_id = f"claim_{c.id}"
            if c.entity_ids:
                try:
                    e_ids = c.entity_ids if isinstance(c.entity_ids, list) else json_module.loads(c.entity_ids)
                    if isinstance(e_ids, list):
                        for eid in e_ids:
                            if eid in node_ids:
                                key = (eid, claim_node_id, "related")
                                if key not in seen_edges:
                                    edges.append({
                                        "source": eid,
                                        "target": claim_node_id,
                                        "type": "related"
                                    })
                                    seen_edges.add(key)
                except (TypeError, ValueError):
                    pass

        # Filter: only include edges where both source and target exist
        edges = [e for e in edges if e["source"] in node_ids and e["target"] in node_ids]

        return {
            "nodes": nodes,
            "edges": edges,
            "article_count": article_count
        }