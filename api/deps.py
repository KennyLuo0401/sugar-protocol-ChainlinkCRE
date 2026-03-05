from fastapi import Request
from db.database import Database
from pipeline.entity_registry import EntityRegistry

def get_db(request: Request) -> Database:
    return request.app.state.db

def get_registry(request: Request) -> EntityRegistry:
    return request.app.state.registry