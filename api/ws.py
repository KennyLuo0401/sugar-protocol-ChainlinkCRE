"""WebSocket endpoint for real-time analysis progress."""

import json
import time
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from pipeline.orchestrator import process_url
from api.sui_bridge import create_market as sui_create_market
from interfaces import FetchError, AnalyzeError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/analyze")
async def ws_analyze(websocket: WebSocket):
    await websocket.accept()

    db = websocket.app.state.db
    registry = websocket.app.state.registry

    try:
        # Wait for client to send URL
        data = await websocket.receive_text()
        payload = json.loads(data)
        url = payload.get("url")
        create_market = payload.get("create_market", False)

        if not url:
            await websocket.send_json({"step": "error", "message": "Missing 'url' field"})
            await websocket.close()
            return

        # Progress callback — pushes events to WebSocket client
        async def on_progress(step: str, progress: float, message: str):
            try:
                await websocket.send_json({
                    "step": step,
                    "progress": progress,
                    "message": message,
                })
            except WebSocketDisconnect:
                logger.warning("Client disconnected during progress: %s", step)

        # Run pipeline
        result = await process_url(url, db, registry, on_progress=on_progress)

        # Auto-create markets for verifiable claims if flag is set
        markets_created = []
        if create_market and result.claims:
            market_claims = [
                c for c in result.claims
                if getattr(c, "potential_market", False) or getattr(c, "verifiable", False)
            ]
            for claim in market_claims[:3]:  # cap at 3 markets per article
                try:
                    await on_progress("market", 0.95, f"Creating market: {claim.text[:40]}...")
                    deadline_ms = int((time.time() + 7 * 86400) * 1000)
                    res = await sui_create_market(claim.text, deadline_ms)
                    if res["success"]:
                        markets_created.append({
                            "claim_text": claim.text,
                            "market_id": res["market_id"],
                            "tx_digest": res["tx_digest"],
                        })
                except Exception as e:
                    logger.warning("Market creation failed for claim: %s", e)

        # Send final result
        final_result = {
            "url": result.url,
            "title": result.title,
            "article_type": result.article_type,
            "analysis_depth": result.analysis_depth,
            "entities": [e.model_dump() for e in result.entities],
            "claims": [c.model_dump() for c in result.claims],
            "edges": [e.model_dump() for e in result.edges],
            "token_usage": result.token_usage,
            "cost": result.cost,
        }
        if markets_created:
            final_result["markets_created"] = markets_created

        await websocket.send_json({
            "step": "done",
            "progress": 1.0,
            "result": final_result,
        })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except (FetchError, AnalyzeError) as e:
        try:
            await websocket.send_json({"step": "error", "message": str(e)})
        except WebSocketDisconnect:
            pass
    except json.JSONDecodeError:
        try:
            await websocket.send_json({"step": "error", "message": "Invalid JSON"})
        except WebSocketDisconnect:
            pass
    except Exception as e:
        logger.exception("Unexpected error in WebSocket handler")
        try:
            await websocket.send_json({"step": "error", "message": str(e)})
        except WebSocketDisconnect:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
