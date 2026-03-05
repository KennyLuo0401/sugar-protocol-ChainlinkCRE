# Sugar Protocol — Session 1 Tests
# Gemini's implementation of fetcher.py and classifier.py MUST pass ALL tests.
# Run: pytest tests/ -v

import pytest
import asyncio
from pipeline.fetcher import fetch_article
from pipeline.classifier import classify_article
from interfaces import (
    FetchResult, FetchMethod, FetchError,
    ClassifyResult, ClassifyError,
    ArticleType, AnalysisDepth,
)


# ═══════════════════════════════════════════
# FETCHER TESTS
# ═══════════════════════════════════════════

class TestFetcher:

    @pytest.mark.asyncio
    async def test_fetch_returns_fetch_result(self):
        """Basic: returns correct type."""
        result = await fetch_article("https://www.bbc.com/news")
        assert isinstance(result, FetchResult)

    @pytest.mark.asyncio
    async def test_fetch_has_content(self):
        """Fetched text should have meaningful content."""
        result = await fetch_article("https://www.bbc.com/news")
        assert result.word_count > 50
        assert len(result.text) > 200

    @pytest.mark.asyncio
    async def test_fetch_title_extracted(self):
        """Title should be non-empty for normal pages."""
        result = await fetch_article("https://www.bbc.com/news")
        assert len(result.title) > 0

    @pytest.mark.asyncio
    async def test_fetch_language_detection_english(self):
        """English site should be detected as en."""
        result = await fetch_article("https://www.bbc.com/news")
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_fetch_language_detection_chinese(self):
        """Chinese site should be detected as zh."""
        # Use a stable Chinese news source
        result = await fetch_article("https://www.cna.com.tw/")
        assert result.language == "zh"

    @pytest.mark.asyncio
    async def test_fetch_method_recorded(self):
        """Should record which method was used."""
        result = await fetch_article("https://www.bbc.com/news")
        assert result.fetch_method in [FetchMethod.JINA, FetchMethod.BS4_FALLBACK]

    @pytest.mark.asyncio
    async def test_fetch_whitespace_cleaned(self):
        """Should not have excessive blank lines."""
        result = await fetch_article("https://www.bbc.com/news")
        # No more than 2 consecutive newlines
        assert "\n\n\n" not in result.text

    @pytest.mark.asyncio
    async def test_fetch_invalid_url_raises(self):
        """Invalid URL should raise FetchError."""
        with pytest.raises(FetchError) as exc_info:
            await fetch_article("https://this-domain-does-not-exist-12345.com/page")
        assert "this-domain-does-not-exist" in exc_info.value.url

    @pytest.mark.asyncio
    async def test_fetch_timeout_respected(self):
        """Very short timeout should fail quickly."""
        # httpbin delays 10 seconds, but we set timeout to 1
        with pytest.raises(FetchError):
            await fetch_article("https://httpbin.org/delay/10", timeout=1)

    @pytest.mark.asyncio
    async def test_fetch_404_raises(self):
        """404 pages should raise FetchError."""
        with pytest.raises(FetchError):
            await fetch_article("https://www.bbc.com/this-page-definitely-does-not-exist-999")

    @pytest.mark.asyncio
    async def test_fetch_word_count_chinese(self):
        """Chinese word count should count characters, not spaces."""
        result = await fetch_article("https://www.cna.com.tw/")
        # Chinese pages typically have many characters
        assert result.char_count > result.word_count * 0.5  # chars >= words for Chinese


# ═══════════════════════════════════════════
# CLASSIFIER TESTS
# ═══════════════════════════════════════════

class TestClassifier:

    def test_returns_classify_result(self):
        """Basic: returns correct type."""
        result = classify_article("這是一篇測試文章，字數不多。")
        assert isinstance(result, ClassifyResult)

    def test_empty_text_raises(self):
        """Empty text should raise ClassifyError."""
        with pytest.raises(ClassifyError):
            classify_article("")

    def test_none_text_raises(self):
        """None text should raise ClassifyError."""
        with pytest.raises(ClassifyError):
            classify_article(None)

    def test_data_recap_short_no_quotes(self):
        """Short text without quotes → DATA_RECAP."""
        text = "台股今日收盤上漲 123 點，收在 22,456 點。成交量 3,200 億元。外資買超 150 億元。"
        result = classify_article(text)
        assert result.article_type == ArticleType.DATA_RECAP
        assert result.analysis_depth == AnalysisDepth.SHALLOW
        assert result.has_quotes == False

    def test_commentary_with_quotes_and_opinions(self):
        """Text with quotes + opinion markers → COMMENTARY."""
        text = """
        台積電今日股價上漲，分析師認為主要受惠於 AI 需求。
        法人表示「未來三個月將持續看好半導體族群」。
        另一位分析師指出，美國晶片法案的落實將進一步推動成長。
        根據統計，台積電 ADR 本週上漲超過 5%，遠優於費城半導體指數。
        市場預測第二季營收將再創新高，主要受惠於蘋果和輝達的訂單。
        投資人擔憂地緣政治風險，但多數法人認為短期內不會影響基本面。
        """ * 2  # repeat to ensure > 500 chars
        result = classify_article(text)
        assert result.article_type == ArticleType.COMMENTARY
        assert result.analysis_depth == AnalysisDepth.FULL
        assert result.has_quotes == True
        assert result.has_opinion_markers == True

    def test_opinion_piece_long_with_opinions(self):
        """Long text with heavy opinion markers → OPINION_PIECE."""
        opinion_sentence = "學者批評政府的做法，認為此舉將嚴重損害國家利益。專家指出這是錯誤的決定。分析人士警告後果不堪設想。"
        text = (opinion_sentence + "\n") * 30  # ~1800+ chars, dense opinion markers
        result = classify_article(text)
        assert result.article_type == ArticleType.OPINION_PIECE
        assert result.analysis_depth == AnalysisDepth.DEEP

    def test_political_controversy_multi_party(self):
        """Text mentioning multiple parties with quotes → POLITICAL_CONTROVERSY."""
        text = """
        國民黨立委今日在立法院強力杯葛國防預算案，民進黨團總召表示「在野黨此舉嚴重危害國防安全」。
        民眾黨立院黨團則認為，預算審查是立法權的核心，不應被強行通過。
        國民黨團書記長批評執政黨「濫用多數暴力」，強調會繼續抵制。
        民進黨立委反駁稱，國防預算攸關國家安全，不容政治操作。
        """ * 2
        result = classify_article(text)
        assert result.article_type == ArticleType.POLITICAL_CONTROVERSY
        assert result.analysis_depth == AnalysisDepth.DEEP

    def test_breaking_news_moderate_length(self):
        """Moderate text, no strong opinion markers → BREAKING_NEWS."""
        text = """
        日本首相高市早苗今日宣布，將於下週訪問華盛頓與美國總統會談。
        雙方預計討論安全合作與經濟議題。外務省發言人說明此行程已規劃數週。
        高市早苗將率領包括經濟產業大臣在內的代表團。訪問將持續三天。
        日本內閣官房長官在記者會上確認了相關安排，但未透露更多細節。
        這將是高市早苗就任以來首次訪美。此前她曾在電話中與美國總統交換意見。
        """
        result = classify_article(text)
        assert result.article_type == ArticleType.BREAKING_NEWS
        assert result.analysis_depth == AnalysisDepth.STANDARD

    def test_quote_detection_chinese_brackets(self):
        """Detects Chinese 「」quotes."""
        text = "某官員表示「我們不會妥協」，這件事情很重要。再次強調不會退讓。" * 5
        result = classify_article(text)
        assert result.has_quotes == True

    def test_quote_detection_english(self):
        """Detects English quote patterns."""
        text = "The minister said the policy would not change. According to sources, talks are ongoing. Officials told reporters that progress was being made." * 5
        result = classify_article(text)
        assert result.has_quotes == True

    def test_opinion_markers_detected(self):
        """Detects opinion/analysis markers."""
        text = "學者認為這項政策有嚴重問題。分析師預測下季將出現反轉。批評者指出政府的回應不足。" * 5
        result = classify_article(text)
        assert result.has_opinion_markers == True

    def test_no_opinion_markers_in_data(self):
        """Pure data text should not flag opinion markers."""
        text = "收盤價 22456 點，上漲 123 點。成交量 3200 億。"
        result = classify_article(text)
        assert result.has_opinion_markers == False

    def test_named_sources_detected(self):
        """Detects named sources in quotes."""
        text = "賴清德表示將持續推動改革。韓國瑜認為應該審慎評估。黃國昌指出程序有瑕疵。" * 5
        result = classify_article(text)
        assert result.has_named_sources == True

    def test_word_count_chinese(self):
        """Chinese word count should roughly equal character count."""
        text = "這是一篇包含五十個中文字的測試文章用來驗證分類器的字數計算功能是否正確地處理了中文文本"
        result = classify_article(text)
        assert 30 < result.word_count < 60

    def test_word_count_english(self):
        """English word count should count space-separated tokens."""
        text = "This is a test article with exactly fourteen words in this English sentence here."
        result = classify_article(text)
        assert 10 < result.word_count < 20

    def test_confidence_in_range(self):
        """Confidence should be between 0 and 1."""
        text = "一些普通的文字內容。" * 20
        result = classify_article(text)
        assert 0.0 <= result.confidence <= 1.0
