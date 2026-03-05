# Sugar Protocol — Pipeline Interfaces
# ⚠️ THIS FILE IS THE CONTRACT. GEMINI MUST NOT MODIFY ANY SIGNATURES.
# If you think something is wrong, add a comment: # INTERFACE_CONCERN: ...

from __future__ import annotations
from pydantic import BaseModel, Field, HttpUrl
from enum import Enum
from typing import Optional
from datetime import datetime


# ═══════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════

class SugarError(Exception):
    """Base exception for all Sugar Protocol errors."""
    pass

class FetchError(SugarError):
    """Raised when article fetching fails after all retries."""
    def __init__(self, url: str, reason: str, method: str = "unknown"):
        self.url = url
        self.reason = reason
        self.method = method
        super().__init__(f"Failed to fetch {url} via {method}: {reason}")

class ClassifyError(SugarError):
    """Raised when classification logic encounters unexpected input."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Classification failed: {reason}")

class AnalyzeError(SugarError):
    """Raised when LLM analysis fails."""
    def __init__(self, reason: str, model: str = "unknown"):
        self.reason = reason
        self.model = model
        super().__init__(f"Analysis failed ({model}): {reason}")

class EntityNotFoundError(SugarError):
    """Raised when an entity lookup fails."""
    def __init__(self, canonical_id: str):
        self.canonical_id = canonical_id
        super().__init__(f"Entity not found: {canonical_id}")

class DuplicateEntityError(SugarError):
    """Raised when attempting to create an entity that already exists."""
    def __init__(self, canonical_id: str):
        self.canonical_id = canonical_id
        super().__init__(f"Duplicate entity: {canonical_id}")


# ═══════════════════════════════════════════
# ENUMS — shared across S2 (LLM) and S3 (pipeline)
# ═══════════════════════════════════════════

class FetchMethod(str, Enum):
    JINA = "jina"
    BS4_FALLBACK = "bs4_fallback"

class ArticleType(str, Enum):
    DATA_RECAP = "data_recap"           # 純數據整理 (e.g., Investing.com 行情)
    COMMENTARY = "commentary"           # 有引述的報導分析 (e.g., Yahoo 新聞)
    OPINION_PIECE = "opinion_piece"     # 社論/深度評論
    BREAKING_NEWS = "breaking_news"     # 速報
    POLITICAL_CONTROVERSY = "political_controversy"  # 政治爭議 (多方立場)

class AnalysisDepth(str, Enum):
    SHALLOW = "shallow"     # data_recap → 只提取數字, ~200 tokens
    STANDARD = "standard"   # breaking_news → L1-L3, ~1000 tokens
    FULL = "full"           # commentary → full L1-L4, ~2000 tokens
    DEEP = "deep"           # opinion_piece / political → L1-L4 + omissions, ~2500 tokens

class EntityTier(str, Enum):
    COUNTRY = "country"
    DOMAIN = "domain"
    EVENT = "event"
    ORGANIZATION = "organization"
    PERSON = "person"
    ASSET = "asset"

class ClaimType(str, Enum):
    FACTUAL = "factual"
    OPINION = "opinion"
    PREDICTION = "prediction"

class EdgeType(str, Enum):
    CONTAINS = "contains"
    DERIVES = "derives"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CAUSAL = "causal"
    RELATED = "related"


# ═══════════════════════════════════════════
# DATA MODELS — S1 (fetcher / classifier)
# ═══════════════════════════════════════════

class FetchResult(BaseModel):
    """Result of fetching a single article."""
    url: str
    title: str = ""
    text: str
    word_count: int
    char_count: int
    fetch_method: FetchMethod
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    language: str = "zh"  # "zh" | "en" — detected from content

class ClassifyResult(BaseModel):
    """Result of classifying an article's type and recommended analysis depth."""
    article_type: ArticleType
    analysis_depth: AnalysisDepth
    has_quotes: bool            # contains 「」or "said"/"according to"
    has_opinion_markers: bool   # contains 認為/表示/預測/believes etc.
    has_named_sources: bool     # quotes attributed to specific people
    word_count: int
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


# ═══════════════════════════════════════════
# DATA MODELS — S3 (pipeline canonical types)
# ═══════════════════════════════════════════

class EntityData(BaseModel):
    """Canonical entity in the discourse graph."""
    canonical_id: str = Field(description="Unique lowercase identifier, e.g. 'tsmc' or 'bitcoin'")
    label: str = Field(description="Display name, e.g. '台積電' or 'Bitcoin'")
    tier: EntityTier
    tier_level: float = Field(default=0, description="Hierarchy depth: 0=root, 1=child, etc.")
    aliases: list[str] = Field(default_factory=list, description="Alternative names")
    belongs_to: Optional[str] = Field(default=None, description="Parent entity canonical_id")
    country: Optional[str] = Field(default=None, description="ISO 3166-1 alpha-2 country code")
    domain: Optional[str] = Field(default=None, description="Domain area, e.g. 'semiconductor', 'crypto'")
    topic: Optional[str] = Field(default=None, description="Topic tag for grouping, e.g. 'us_tariff'")

class ClaimData(BaseModel):
    """A single claim extracted from an article."""
    text: str = Field(description="The claim text")
    claim_type: ClaimType = Field(default=ClaimType.FACTUAL)
    verifiable: bool = Field(default=True, description="Can this claim be fact-checked?")
    verify_how: Optional[str] = Field(default=None, description="How to verify this claim")
    debatable: bool = Field(default=False, description="Is this claim controversial/debatable?")
    potential_market: bool = Field(default=False, description="Could this be a prediction market?")
    source_article_url: Optional[str] = Field(default=None, description="URL of the source article")
    source_in_article: Optional[str] = Field(default=None, description="Quote or paragraph in article supporting this claim")
    entity_ids: list[str] = Field(default_factory=list, description="canonical_ids of entities related to this claim")

class ArticleData(BaseModel):
    """Metadata for a processed article."""
    url: str
    title: str = ""
    article_type: ArticleType = Field(default=ArticleType.BREAKING_NEWS)
    analysis_depth: AnalysisDepth = Field(default=AnalysisDepth.STANDARD)
    language: str = "zh"
    raw_analysis_json: str | dict = Field(default="", description="Raw JSON from LLM analysis")

class EdgeData(BaseModel):
    """A directed edge in the discourse graph."""
    source_id: str = Field(description="canonical_id or claim index of source node")
    target_id: str = Field(description="canonical_id or claim index of target node")
    edge_type: EdgeType
    note: str = Field(default="", description="Brief explanation of the relationship")

class EntityMatch(BaseModel):
    """Result of entity deduplication / matching."""
    canonical_id: str
    label: str
    tier: EntityTier
    match_type: str = Field(default="exact", description="exact | fuzzy | alias")
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


# ═══════════════════════════════════════════
# FUNCTION SIGNATURES — Gemini implements these
# ═══════════════════════════════════════════

# ---- fetcher.py ----

async def fetch_article(url: str, timeout: int = 15) -> FetchResult:
    """
    Fetch and extract article text from a URL.

    Strategy (in order):
    1. Try Jina Reader API: GET https://r.jina.ai/{url}
       - Set header: Accept: text/plain
       - Jina returns clean markdown text
       - Parse title from first # heading if present
    2. If Jina fails (timeout, 4xx, 5xx), fallback to:
       - httpx.AsyncClient GET the URL directly
       - BeautifulSoup with html.parser
       - Extract text from <article>, or <main>, or <body> (in that order)
       - Extract title from <title> or <h1>
    3. If both fail, raise FetchError

    Post-processing (both methods):
    - Strip excessive whitespace (collapse multiple \n to max 2)
    - Remove common boilerplate: cookie notices, nav menus, footer
    - Detect language: if >50% characters are CJK → "zh", else "en"
    - Count words: for zh, count characters (excluding punctuation); for en, split by space

    Returns: FetchResult
    Raises: FetchError if all methods fail
    """
    ...


# ---- classifier.py ----

def classify_article(text: str) -> ClassifyResult:
    """
    Classify article type using ONLY regex/heuristics. No LLM calls.

    Rules (apply in order, first match wins):

    1. POLITICAL_CONTROVERSY (highest priority):
       - Contains 2+ different political party names (國民黨/民進黨/民眾黨/KMT/DPP/TPP)
       - AND contains quote markers AND opinion markers
       - → analysis_depth = DEEP

    2. OPINION_PIECE:
       - word_count > 1500
       - AND has_opinion_markers = True
       - AND opinion_marker_density > 3 per 1000 chars
       - → analysis_depth = DEEP

    3. COMMENTARY:
       - has_quotes = True AND has_opinion_markers = True
       - → analysis_depth = FULL

    4. BREAKING_NEWS:
       - word_count > 300
       - has_quotes may be True or False
       - → analysis_depth = STANDARD

    5. DATA_RECAP (lowest priority / default):
       - word_count < 500 AND has_quotes = False
       - → analysis_depth = SHALLOW

    Quote detection patterns (regex):
    - Chinese: [「『【《].*?[」』】》]
    - English: said|says|according to|told reporters

    Opinion marker patterns:
    - Chinese: 認為|表示|指出|批評|強調|呼籲|預測|擔憂|主張|質疑|警告|分析
    - English: believes?|argues?|suggests?|warns?|predicts?|claims?

    Named source detection:
    - Chinese: [name]表示|[name]認為|[name]指出 where [name] is 2-4 CJK chars
    - English: [Name] said|according to [Name]

    Political party detection (for POLITICAL_CONTROVERSY):
    - 國民黨|KMT|藍營|藍委
    - 民進黨|DPP|綠營|綠委
    - 民眾黨|TPP|白營|柯文哲
    - 自民黨|LDP|共和黨|民主黨
    - Count unique parties found; if >= 2 → multi_party = True

    Returns: ClassifyResult
    Raises: ClassifyError if text is empty or None
    """
    ...
