from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from api.deps import get_db, get_registry
from db.database import Database
from db.models import ClaimModel
from pipeline.entity_registry import EntityRegistry

router = APIRouter()

@router.get("/search")
async def search_data(
    q: str = Query(..., min_length=1),
    db: Database = Depends(get_db),
    registry: EntityRegistry = Depends(get_registry)
):
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    # Entities: 呼叫 registry.search
    found_entities = await registry.search(q)
    
    # Claims: SQLAlchemy 模糊搜尋
    claims_list = []
    async with db.session() as session:
        stmt = select(ClaimModel).where(ClaimModel.text.contains(q))
        result = await session.execute(stmt)
        found_claims = result.scalars().all()
        
        for c in found_claims:
            claims_list.append({
                "id": c.id,
                "text": c.text,
                "claim_type": c.claim_type,
                "source_article_url": c.source_article_url
            })

    return {
        "query": q,
        "entities": [e.model_dump() for e in found_entities],
        "claims": claims_list
    }