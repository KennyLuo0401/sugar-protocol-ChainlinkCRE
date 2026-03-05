# Sugar Protocol — Framework C Prompt Templates
# Generates system prompts for LLM analysis at different depth levels.

from __future__ import annotations

from interfaces import AnalysisDepth


# ═══════════════════════════════════════════
# FEW-SHOT EXAMPLES
# ═══════════════════════════════════════════

_EXAMPLE_SHALLOW = """{
  "article_type": "data_recap",
  "entities": [
    {"canonical_id": "tsmc", "label": "台積電", "tier": "organization", "aliases": ["TSMC", "2330"], "country": "TW", "domain": "semiconductor"}
  ],
  "claims": [
    {"text": "台積電股價上漲3.2%", "type": "factual", "verifiable": true, "debatable": false, "potential_market": false, "source_entities": []}
  ]
}"""

_EXAMPLE_STANDARD = """{
  "article_type": "breaking_news",
  "entities": [
    {"canonical_id": "bitcoin", "label": "比特幣", "tier": "domain", "aliases": ["BTC"], "domain": "crypto"},
    {"canonical_id": "microstrategy", "label": "MicroStrategy", "tier": "organization", "aliases": ["MSTR"], "country": "US", "domain": "crypto"}
  ],
  "claims": [
    {"text": "MicroStrategy再次購入5000枚比特幣", "type": "factual", "verifiable": true, "debatable": false, "potential_market": false, "source_entities": ["microstrategy"]},
    {"text": "此次購買均價約為62,000美元", "type": "factual", "verifiable": true, "debatable": false, "potential_market": false, "source_entities": ["microstrategy"]},
    {"text": "比特幣短期內可能突破70,000美元", "type": "prediction", "verifiable": false, "debatable": true, "potential_market": true, "source_entities": []}
  ],
  "conflict_graph": []
}"""

_EXAMPLE_FULL = """{
  "article_type": "commentary",
  "entities": [
    {"canonical_id": "fed", "label": "聯準會", "tier": "organization", "aliases": ["Fed", "Federal Reserve"], "country": "US", "domain": "central_bank"},
    {"canonical_id": "jerome_powell", "label": "鮑威爾", "tier": "person", "aliases": ["Jerome Powell"], "belongs_to": "fed", "country": "US"}
  ],
  "claims": [
    {"text": "聯準會暗示年底前可能降息", "type": "factual", "verifiable": true, "debatable": false, "potential_market": true, "source_entities": ["fed", "jerome_powell"]},
    {"text": "通膨已出現明顯下降趨勢", "type": "opinion", "verifiable": true, "debatable": true, "potential_market": false, "source_entities": ["jerome_powell"]},
    {"text": "市場過度樂觀，降息時間可能延後", "type": "opinion", "verifiable": false, "debatable": true, "potential_market": true, "source_entities": []}
  ],
  "conflict_graph": [
    {"source_claim_idx": 0, "target_claim_idx": 2, "edge_type": "contradicts", "description": "聯準會暗示降息 vs 分析師認為可能延後"}
  ]
}"""

_EXAMPLE_DEEP = """{
  "article_type": "political_controversy",
  "entities": [
    {"canonical_id": "kmt", "label": "國民黨", "tier": "organization", "aliases": ["KMT", "藍營"], "country": "TW", "domain": "politics"},
    {"canonical_id": "dpp", "label": "民進黨", "tier": "organization", "aliases": ["DPP", "綠營"], "country": "TW", "domain": "politics"}
  ],
  "claims": [
    {"text": "國民黨主張兩岸應恢復對話", "type": "opinion", "verifiable": false, "debatable": true, "potential_market": false, "source_entities": ["kmt"]},
    {"text": "民進黨認為對話前提是對岸放棄武力威脅", "type": "opinion", "verifiable": false, "debatable": true, "potential_market": false, "source_entities": ["dpp"]}
  ],
  "omissions": [
    {"description": "未提及民眾黨的第三方立場", "perspective": "民眾黨/中間選民", "importance": 0.7},
    {"description": "缺少國際社會對兩岸關係的看法", "perspective": "國際觀察者", "importance": 0.5}
  ],
  "conflict_graph": [
    {"source_claim_idx": 0, "target_claim_idx": 1, "edge_type": "contradicts", "description": "藍綠對兩岸對話前提的根本分歧"}
  ]
}"""

_EXAMPLES = {
    AnalysisDepth.SHALLOW: _EXAMPLE_SHALLOW,
    AnalysisDepth.STANDARD: _EXAMPLE_STANDARD,
    AnalysisDepth.FULL: _EXAMPLE_FULL,
    AnalysisDepth.DEEP: _EXAMPLE_DEEP,
}


# ═══════════════════════════════════════════
# INSTRUCTIONS PER DEPTH
# ═══════════════════════════════════════════

_INSTRUCTIONS_ZH = {
    AnalysisDepth.SHALLOW: """你是 Sugar Protocol 的新聞分析引擎。請從文章中提取：
1. **entities**: 文中提到的主要實體（公司、人物、國家等），每個包含 canonical_id、label、tier、aliases、country、domain
2. **claims**: 文中的關鍵數據和事實陳述

這是一篇數據摘要類文章，只需提取具體數字和事實，不需要分析觀點。
輸出上限約 200 tokens。""",

    AnalysisDepth.STANDARD: """你是 Sugar Protocol 的新聞分析引擎。請從文章中提取：
1. **entities**: 文中提到的主要實體，每個包含 canonical_id、label、tier、aliases、belongs_to（如適用）、country、domain
2. **claims**: 文中的主要論點和事實陳述，每個標注 type（factual/opinion/prediction）、verifiable、debatable、potential_market、source_entities
3. **conflict_graph**: 如果有互相矛盾的 claims，標註它們之間的關係

這是一篇速報類文章，請提取主要事實和關鍵引述。
輸出上限約 1000 tokens。""",

    AnalysisDepth.FULL: """你是 Sugar Protocol 的新聞分析引擎。請從文章中完整提取四層言論拓撲：
1. **entities**: 所有相關實體，每個包含 canonical_id、label、tier、aliases、belongs_to、country、domain
2. **claims**: 所有論點和事實陳述，每個標注 type（factual/opinion/prediction）、verifiable、debatable、potential_market、source_entities
3. **conflict_graph**: 所有 claims 之間的支持（supports）、矛盾（contradicts）或因果（causal）關係

這是一篇深度報導，請仔細分析各方觀點和它們之間的關係。
輸出上限約 2000 tokens。""",

    AnalysisDepth.DEEP: """你是 Sugar Protocol 的新聞分析引擎。請從文章中完整提取四層言論拓撲，並特別注意被遺漏的觀點：
1. **entities**: 所有相關實體，每個包含 canonical_id、label、tier、aliases、belongs_to、country、domain
2. **claims**: 所有論點和事實陳述，每個標注 type（factual/opinion/prediction）、verifiable、debatable、potential_market、source_entities
3. **omissions**: 文章遺漏了哪些重要觀點或利害關係人的立場？誰的聲音沒有被呈現？
4. **conflict_graph**: 所有 claims 之間的支持（supports）、矛盾（contradicts）或因果（causal）關係，並附簡短說明

這是一篇涉及爭議的深度分析文章，請特別注意：
- 是否有某一方的立場被過度呈現？
- 是否有重要的反對意見被省略？
- 是否有潛在的預測市場機會？
輸出上限約 2500 tokens。""",
}

_INSTRUCTIONS_EN = {
    AnalysisDepth.SHALLOW: """You are the Sugar Protocol news analysis engine. Extract from the article:
1. **entities**: Key entities mentioned (companies, people, countries, etc.) with canonical_id, label, tier, aliases, country, domain
2. **claims**: Key data points and factual statements

This is a data recap article. Only extract concrete numbers and facts, no opinion analysis needed.
Output limit: ~200 tokens.""",

    AnalysisDepth.STANDARD: """You are the Sugar Protocol news analysis engine. Extract from the article:
1. **entities**: Key entities with canonical_id, label, tier, aliases, belongs_to (if applicable), country, domain
2. **claims**: Main claims and factual statements, each tagged with type (factual/opinion/prediction), verifiable, debatable, potential_market, source_entities
3. **conflict_graph**: If any claims contradict each other, note the relationships

This is a breaking news article. Extract key facts and notable quotes.
Output limit: ~1000 tokens.""",

    AnalysisDepth.FULL: """You are the Sugar Protocol news analysis engine. Extract the full four-layer discourse topology:
1. **entities**: All relevant entities with canonical_id, label, tier, aliases, belongs_to, country, domain
2. **claims**: All claims and factual statements, each tagged with type (factual/opinion/prediction), verifiable, debatable, potential_market, source_entities
3. **conflict_graph**: All supports, contradicts, or causal relationships between claims

This is an in-depth report. Carefully analyze different perspectives and their relationships.
Output limit: ~2000 tokens.""",

    AnalysisDepth.DEEP: """You are the Sugar Protocol news analysis engine. Extract the full four-layer discourse topology, paying special attention to omitted perspectives:
1. **entities**: All relevant entities with canonical_id, label, tier, aliases, belongs_to, country, domain
2. **claims**: All claims and factual statements, each tagged with type (factual/opinion/prediction), verifiable, debatable, potential_market, source_entities
3. **omissions**: What important perspectives or stakeholder positions are missing? Whose voice is not represented?
4. **conflict_graph**: All supports, contradicts, or causal relationships between claims, with brief descriptions

This is a controversial deep-analysis article. Pay special attention to:
- Is any side's position over-represented?
- Are important opposing views omitted?
- Are there potential prediction market opportunities?
Output limit: ~2500 tokens.""",
}


# ═══════════════════════════════════════════
# COMMON SCHEMA INSTRUCTION
# ═══════════════════════════════════════════

_SCHEMA_INSTRUCTION_ZH = """
你必須以 JSON 格式回覆。JSON 結構如下：
{
  "article_type": "string (data_recap | commentary | opinion_piece | breaking_news | political_controversy)",
  "entities": [{"canonical_id": "string", "label": "string", "tier": "country|domain|event|organization|person", "aliases": ["string"], "belongs_to": "string|null", "country": "string|null", "domain": "string|null"}],
  "claims": [{"text": "string", "type": "factual|opinion|prediction", "verifiable": bool, "debatable": bool, "potential_market": bool, "source_entities": ["canonical_id"]}],
  "omissions": [{"description": "string", "perspective": "string", "importance": float}],
  "conflict_graph": [{"source_claim_idx": int, "target_claim_idx": int, "edge_type": "supports|contradicts|causal", "description": "string"}]
}

重要規則：
- canonical_id 必須是小寫英文，用底線分隔（如 "micro_strategy"）
- source_entities 中的值必須對應 entities 中的 canonical_id
- conflict_graph 中的 idx 必須對應 claims 陣列的索引
- 只輸出 JSON，不要有任何其他文字
"""

_SCHEMA_INSTRUCTION_EN = """
You MUST respond in JSON format. The JSON structure is:
{
  "article_type": "string (data_recap | commentary | opinion_piece | breaking_news | political_controversy)",
  "entities": [{"canonical_id": "string", "label": "string", "tier": "country|domain|event|organization|person", "aliases": ["string"], "belongs_to": "string|null", "country": "string|null", "domain": "string|null"}],
  "claims": [{"text": "string", "type": "factual|opinion|prediction", "verifiable": bool, "debatable": bool, "potential_market": bool, "source_entities": ["canonical_id"]}],
  "omissions": [{"description": "string", "perspective": "string", "importance": float}],
  "conflict_graph": [{"source_claim_idx": int, "target_claim_idx": int, "edge_type": "supports|contradicts|causal", "description": "string"}]
}

Important rules:
- canonical_id must be lowercase English with underscores (e.g. "micro_strategy")
- source_entities values must match canonical_id values in entities
- conflict_graph idx values must reference claims array indices
- Output ONLY JSON, no other text
"""


# ═══════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════

def get_system_prompt(depth: AnalysisDepth, language: str = "zh") -> str:
    """Build a complete system prompt for the given analysis depth and language.

    Args:
        depth: Analysis depth level (SHALLOW, STANDARD, FULL, DEEP).
        language: "zh" for Chinese instructions, "en" for English.

    Returns:
        Complete system prompt string with instructions, schema, and few-shot example.
    """
    if language == "en":
        instructions = _INSTRUCTIONS_EN[depth]
        schema_instruction = _SCHEMA_INSTRUCTION_EN
    else:
        instructions = _INSTRUCTIONS_ZH[depth]
        schema_instruction = _SCHEMA_INSTRUCTION_ZH

    example = _EXAMPLES[depth]
    example_label = "範例輸出" if language != "en" else "Example output"

    return f"""{instructions}
{schema_instruction}
{example_label}:
```json
{example}
```"""
