# Sugar Protocol — LLM Output Schemas
# Pydantic models for validating raw structured JSON from LLM analysis.
#
# These "Raw" models match the LLM's JSON output format, which differs
# from the canonical pipeline models in interfaces.py:
#   - RawEntityData.tier has no "asset" (LLM doesn't output it)
#   - RawClaimData uses "type" (LLM outputs "type"), vs ClaimData.claim_type
#   - RawClaimData uses "source_entities", vs ClaimData.entity_ids
#   - ConflictEdge uses claim array indices, vs EdgeData uses entity/claim IDs

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

# Shared enums — single source of truth in interfaces.py
from interfaces import ClaimType, EdgeType, EntityTier


class RawEntityData(BaseModel):
    """Entity as returned by LLM JSON output."""
    canonical_id: str = Field(description="Unique lowercase identifier, e.g. 'tsmc' or 'bitcoin'")
    label: str = Field(description="Display name, e.g. '台積電' or 'Bitcoin'")
    tier: EntityTier
    aliases: list[str] = Field(default_factory=list, description="Alternative names")
    belongs_to: Optional[str] = Field(default=None, description="Parent entity canonical_id")
    country: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2 country code")
    domain: Optional[str] = Field(default=None, description="Domain area, e.g. 'semiconductor', 'crypto'")


class RawClaimData(BaseModel):
    """Claim as returned by LLM JSON output."""
    text: str = Field(description="The claim text")
    type: ClaimType = Field(default=ClaimType.FACTUAL)
    verifiable: bool = Field(default=True, description="Can this claim be fact-checked?")
    debatable: bool = Field(default=False, description="Is this claim controversial/debatable?")
    potential_market: bool = Field(default=False, description="Could this be turned into a prediction market?")
    source_entities: list[str] = Field(default_factory=list, description="canonical_ids of entities making this claim")


class OmissionData(BaseModel):
    """An omitted perspective identified by LLM."""
    description: str = Field(description="What perspective or fact is missing")
    perspective: str = Field(description="Whose perspective is omitted")
    importance: float = Field(ge=0.0, le=1.0, default=0.5, description="How important is this omission (0-1)")


class ConflictEdge(BaseModel):
    """A conflict/support edge between claims, using array indices (LLM output format)."""
    source_claim_idx: int = Field(description="Index of source claim in claims[]")
    target_claim_idx: int = Field(description="Index of target claim in claims[]")
    edge_type: EdgeType
    description: str = Field(default="", description="Brief explanation of the relationship")


class TokenUsage(BaseModel):
    """OpenAI API token usage tracking."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AnalysisResult(BaseModel):
    """Complete result from LLM analysis of a single article."""
    article_type: str = Field(description="Echoed from classifier or inferred by LLM")
    entities: list[RawEntityData] = Field(default_factory=list)
    claims: list[RawClaimData] = Field(default_factory=list)
    omissions: list[OmissionData] = Field(default_factory=list)
    conflict_graph: list[ConflictEdge] = Field(default_factory=list)
    raw_response: str = Field(default="", description="Raw JSON string from LLM")
    model: str = Field(default="")
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    cost: float = Field(default=0.0, description="Estimated cost in USD")
