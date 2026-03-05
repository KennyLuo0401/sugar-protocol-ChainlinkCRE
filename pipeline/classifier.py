import re
from typing import List

from interfaces import (
    ClassifyResult,
    ArticleType,
    AnalysisDepth,
    ClassifyError
)


def classify_article(text: str) -> ClassifyResult:
    """
    Classifies an article based on regex patterns and heuristics.
    """
    if text is None:
        raise ClassifyError("Text cannot be None")
    if not text.strip():
        raise ClassifyError("Text cannot be empty")

    # 1. Feature Extraction
    has_quotes = _check_quotes(text)
    has_opinion_markers = _check_opinion_markers(text)
    has_named_sources = _check_named_sources(text)
    
    cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if cjk_count > len(text) * 0.3:
        word_count = cjk_count
    else:
        word_count = len(text.split())

    # 2. Score Categories
    is_political = _check_political_controversy(text)
    is_breaking = _check_breaking_news(text)
    is_financial_data = _check_financial_data(text)
    
    # 3. Decision Tree / Logic
    article_type = ArticleType.DATA_RECAP
    analysis_depth = AnalysisDepth.SHALLOW
    confidence = 0.8

    if is_political:
        article_type = ArticleType.POLITICAL_CONTROVERSY
        analysis_depth = AnalysisDepth.DEEP
        confidence = 0.95
    
    elif is_breaking:
        article_type = ArticleType.BREAKING_NEWS
        analysis_depth = AnalysisDepth.STANDARD
        confidence = 0.85

    # Revised Logic: Market Commentary vs Opinion Piece
    # If it has financial data, we prioritize COMMENTARY even if it has opinions.
    elif is_financial_data and (has_opinion_markers or has_quotes):
        article_type = ArticleType.COMMENTARY
        analysis_depth = AnalysisDepth.FULL
        confidence = 0.9

    elif has_opinion_markers and has_quotes:
        # If no financial data but has opinions + quotes + length -> Opinion Piece
        if _count_opinion_markers(text) > 10 or word_count > 800:
             article_type = ArticleType.OPINION_PIECE
             analysis_depth = AnalysisDepth.DEEP
             confidence = 0.9
        else:
             article_type = ArticleType.COMMENTARY
             analysis_depth = AnalysisDepth.FULL
             confidence = 0.85
        
    elif has_opinion_markers and word_count > 200:
        article_type = ArticleType.OPINION_PIECE
        analysis_depth = AnalysisDepth.DEEP
        confidence = 0.85
        
    elif is_financial_data:
        article_type = ArticleType.DATA_RECAP
        analysis_depth = AnalysisDepth.SHALLOW
        confidence = 0.95
    
    else:
        if has_quotes and word_count > 150:
             article_type = ArticleType.COMMENTARY
             analysis_depth = AnalysisDepth.STANDARD
        elif word_count < 100:
            article_type = ArticleType.DATA_RECAP
            analysis_depth = AnalysisDepth.SHALLOW

    return ClassifyResult(
        article_type=article_type,
        analysis_depth=analysis_depth,
        has_quotes=has_quotes,
        has_opinion_markers=has_opinion_markers,
        has_named_sources=has_named_sources,
        word_count=word_count,
        confidence=confidence
    )


# ═══════════════════════════════════════════
# HELPER FUNCTIONS (REGEX)
# ═══════════════════════════════════════════

def _check_quotes(text: str) -> bool:
    # Explicit quotes
    if re.search(r'[「『"“](.*?)[」』”"]', text):
        return True
    
    # Indirect speech (English) - "said", "told", etc.
    # Essential for test_quote_detection_english
    indirect_pattern = r'\b(said|told|stated|according to|reported|announced)\b'
    if re.search(indirect_pattern, text, re.IGNORECASE):
        return True
        
    return False


def _check_opinion_markers(text: str) -> bool:
    keywords = [
        "認為", "表示", "指出", "批評", "警告", "建議", "強調", "分析",
        "think", "believe", "said", "stated", "warned", "suggested", "argued", "according to"
    ]
    for k in keywords:
        if k in text:
            return True
    return False


def _count_opinion_markers(text: str) -> int:
    keywords = [
        "認為", "表示", "指出", "批評", "警告", "建議", "強調", "分析",
        "think", "believe", "said", "stated", "warned", "suggested", "argued"
    ]
    count = 0
    for k in keywords:
        count += text.count(k)
    return count


def _check_named_sources(text: str) -> bool:
    zh_pattern = r'[\u4e00-\u9fa5]{2,4}(?:表示|認為|指出|說|強調)'
    if re.search(zh_pattern, text):
        return True
        
    en_pattern = r'[A-Z][a-z]+ (?:said|stated|told|announced)'
    if re.search(en_pattern, text):
        return True
    
    keywords = ["官員", "sources", "officials", "minister", "立委", "總統"]
    for k in keywords:
        if k.lower() in text.lower():
            return True
            
    return False


def _check_political_controversy(text: str) -> bool:
    keywords = [
        "國民黨", "民進黨", "民眾黨", "立法院", "國會", "杯葛", "黨團", 
        "Kuomintang", "DPP", "KMT", "parliament", "congress", "opposition party"
    ]
    matches = 0
    for k in keywords:
        if k.lower() in text.lower():
            matches += 1
            
    conflict_words = ["批評", "反駁", "抵制", "oppose", "criticize", "reject", "abuse"]
    has_conflict = any(cw in text.lower() for cw in conflict_words)
    
    return matches >= 1 and has_conflict


def _check_breaking_news(text: str) -> bool:
    keywords = [
        "宣布", "突發", "快訊", "訪問", "行程", "會談",
        "announce", "breaking", "visit", "meeting", "scheduled"
    ]
    matches = 0
    for k in keywords:
        if k in text.lower():
            matches += 1
            
    return matches >= 1 and len(text) < 1000


def _check_financial_data(text: str) -> bool:
    keywords = [
        "收盤", "上漲", "下跌", "點", "成交量", "億元", "營收", "股價",
        "closed at", "rose", "fell", "points", "turnover", "revenue", "share price"
    ]
    matches = 0
    for k in keywords:
        if k in text.lower():
            matches += 1
    
    digit_count = sum(c.isdigit() for c in text)
    # Relaxed density check if we have strong keywords
    is_number_heavy = digit_count / len(text) > 0.02 if len(text) > 0 else False
    
    # If 3 or more keywords are present, assume financial data even if digits are sparse
    if matches >= 3:
        return True
        
    return matches >= 1 and is_number_heavy