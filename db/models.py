"""SQLAlchemy ORM models for Sugar Protocol."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, Boolean, Float, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EntityModel(Base):
    __tablename__ = "entities"

    canonical_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    tier_level: Mapped[int] = mapped_column(Integer, default=0)
    aliases: Mapped[Optional[str]] = mapped_column(JSON, default=list)
    belongs_to: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    topic: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class ClaimModel(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), default="factual")
    verifiable: Mapped[bool] = mapped_column(Boolean, default=True)
    verify_how: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    debatable: Mapped[bool] = mapped_column(Boolean, default=False)
    potential_market: Mapped[bool] = mapped_column(Boolean, default=False)
    source_article_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity_ids: Mapped[Optional[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class ArticleModel(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, default="")
    article_type: Mapped[str] = mapped_column(String(32), default="breaking_news")
    analysis_depth: Mapped[str] = mapped_column(String(16), default="standard")
    language: Mapped[str] = mapped_column(String(8), default="zh")
    raw_analysis_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class EdgeModel(Base):
    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    edge_type: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
