from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc

from api.deps import get_db, get_registry
from db.database import Database
from db.models import ArticleModel
from pipeline.entity_registry import EntityRegistry
from pipeline.orchestrator import process_url
from interfaces import FetchError, AnalyzeError

router = APIRouter()

class AnalyzeRequest(BaseModel):
    url: str

@router.post("/analyze")
async def analyze_article(
    request: AnalyzeRequest,
    db: Database = Depends(get_db),
    registry: EntityRegistry = Depends(get_registry),
):
    # Check if URL was already analyzed
    async with db.session() as session:
        existing = await session.execute(
            select(ArticleModel).where(ArticleModel.url == request.url)
        )
        if existing.scalar():
            raise HTTPException(
                status_code=409,
                detail=f"This URL has already been analyzed: {request.url}"
            )

    try:
        # 呼叫 orchestrator
        result = await process_url(request.url, db, registry)
        
        # 轉換結果為 dict
        response = {
            "status": "ok",
            "url": result.url,
            "title": result.title,
            "article_type": result.article_type,
            "analysis_depth": result.analysis_depth,
            # EntityMatch 是 Pydantic model
            "entities": [e.model_dump() for e in result.entities],
            # ClaimData 是 Pydantic model
            "claims": [c.model_dump() for c in result.claims],
            # EdgeData 是 Pydantic model
            "edges": [e.model_dump() for e in result.edges],
            "token_usage": result.token_usage,
            "cost": result.cost,
        }
        return response

    except (FetchError, AnalyzeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/articles")
async def list_articles(db: Database = Depends(get_db)):
    async with db.session() as session:
        # 按 analyzed_at 降序排列
        stmt = select(ArticleModel).order_by(desc(ArticleModel.analyzed_at))
        result = await session.execute(stmt)
        articles = result.scalars().all()

        article_list = []
        for a in articles:
            article_list.append({
                "id": a.id,
                "url": a.url,
                "title": a.title,
                "article_type": a.article_type,
                "analysis_depth": a.analysis_depth,
                "language": a.language,
                "analyzed_at": a.analyzed_at.isoformat() if a.analyzed_at else None
            })

        return {
            "articles": article_list,
            "total": len(article_list)
        }