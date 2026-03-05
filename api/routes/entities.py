from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from api.deps import get_registry
from pipeline.entity_registry import EntityRegistry
from interfaces import EntityNotFoundError, EntityTier

router = APIRouter()

@router.get("/entities")
async def list_entities(
    tier: Optional[str] = None,
    registry: EntityRegistry = Depends(get_registry)
):
    tier_filter = None
    if tier:
        try:
            tier_filter = EntityTier(tier.lower())
        except ValueError:
            valid = ", ".join(t.value for t in EntityTier)
            raise HTTPException(status_code=400, detail=f"Invalid tier '{tier}'. Valid: {valid}")

    entities = await registry.list_all(tier=tier_filter)
    
    # 轉換 Pydantic model 為 dict
    entity_list = [e.model_dump() for e in entities]
    
    return {
        "entities": entity_list,
        "total": len(entity_list)
    }

@router.get("/entities/{canonical_id}")
async def get_entity(
    canonical_id: str,
    registry: EntityRegistry = Depends(get_registry)
):
    try:
        entity = await registry.get(canonical_id)
        return entity.model_dump()
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))