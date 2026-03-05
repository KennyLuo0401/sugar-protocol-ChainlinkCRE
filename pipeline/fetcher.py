import asyncio
import re
from datetime import datetime, timezone
from typing import Tuple, Optional

import httpx
from bs4 import BeautifulSoup

from config import (
    JINA_BASE_URL,
    FETCH_TIMEOUT,
    FETCH_MAX_RETRIES,
    USER_AGENT,
)
from interfaces import (
    FetchResult,
    FetchMethod,
    FetchError,
)


async def fetch_article(url: str, timeout: int = FETCH_TIMEOUT) -> FetchResult:
    """
    Fetches article content from a URL using Jina Reader with a BS4 fallback.
    """
    if not url.startswith(("http://", "https://")):
        raise FetchError(url, "Invalid URL schema", method="validation")
    
    # 1. Try Jina Reader
    try:
        return await _fetch_via_jina(url, timeout)
    except Exception:
        # 2. Fallback to BeautifulSoup if Jina fails
        try:
            return await _fetch_via_bs4(url, timeout)
        except Exception as e:
            if isinstance(e, FetchError):
                raise e
            raise FetchError(url, str(e), method="bs4_fallback")


async def _fetch_via_jina(target_url: str, timeout: int) -> FetchResult:
    """Fetches content using the Jina Reader API."""
    jina_url = f"{JINA_BASE_URL}{target_url}"
    headers = {"Accept": "text/plain", "User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(jina_url, headers=headers)
            
            if response.status_code == 404:
                raise FetchError(target_url, "404 Not Found", method="jina")
            
            # Check for Jina specific error texts or soft 404s
            text = response.text
            if "Page not found" in text[:200] or "404" in text[:200]:
                 raise FetchError(target_url, "Soft 404 detected in Jina response", method="jina")

            response.raise_for_status()

            lines = text.splitlines()
            title = ""
            clean_lines = []
            
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                # Heuristic 1: Markdown Header (# Title)
                if not title and stripped.startswith("#"):
                    title = stripped.lstrip("#").strip()
                    continue

                # Heuristic 2: explicit "Title:" metadata (Fix for failed test case)
                if not title and stripped.startswith("Title: "):
                    title = stripped.replace("Title: ", "", 1).strip()
                    continue

                # Heuristic 3: Filter out Jina metadata lines if present
                if stripped.startswith("URL Source:") or stripped.startswith("Markdown Content:"):
                    continue

                clean_lines.append(stripped)
            
            content = "\n".join(clean_lines)
            
            if not content:
                # If content is empty but we have raw text, fall back to raw text
                # (This happens if heuristics stripped everything mistakenly)
                if text.strip():
                    content = text
                else:
                    raise ValueError("Empty content from Jina")

            # Fallback for title: if no header found, use the first line if it's short
            if not title and clean_lines:
                first_line = clean_lines[0]
                if len(first_line) < 100:
                    title = first_line

            return _create_result(
                url=target_url,
                title=title,
                text=content,
                method=FetchMethod.JINA
            )

        except httpx.TimeoutException:
            raise FetchError(target_url, "Timeout", method="jina")
        except httpx.HTTPStatusError as e:
            raise FetchError(target_url, f"HTTP {e.response.status_code}", method="jina")
        except Exception as e:
            raise FetchError(target_url, str(e), method="jina")


async def _fetch_via_bs4(url: str, timeout: int) -> FetchResult:
    """Fetches content using direct HTTP request and BeautifulSoup parsing."""
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 404:
                raise FetchError(url, "404 Not Found", method="bs4_fallback")
                
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            title = ""
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            
            # Stronger Soft 404 detection for BS4
            title_lower = title.lower()
            if "404" in title_lower or "page not found" in title_lower or "doesn't exist" in title_lower:
                raise FetchError(url, "Soft 404 detected in Title", method="bs4_fallback")

            for script in soup(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
                script.decompose()
            
            text_blocks = []
            for p in soup.find_all("p"):
                text = p.get_text().strip()
                if text:
                    text_blocks.append(text)
            
            content = "\n".join(text_blocks)
            
            if not content:
                content = soup.get_text(separator="\n").strip()

            content = re.sub(r'\n\s*\n', '\n\n', content)

            if not content:
                raise ValueError("Empty content extracted via BS4")

            return _create_result(
                url=url,
                title=title,
                text=content,
                method=FetchMethod.BS4_FALLBACK
            )

        except httpx.TimeoutException:
            raise FetchError(url, "Timeout", method="bs4_fallback")
        except httpx.HTTPStatusError as e:
            raise FetchError(url, f"HTTP {e.response.status_code}", method="bs4_fallback")
        except Exception as e:
            raise FetchError(url, str(e), method="bs4_fallback")


def _create_result(url: str, title: str, text: str, method: FetchMethod) -> FetchResult:
    language = _detect_language(text)
    word_count, char_count = _calculate_counts(text, language)
    
    return FetchResult(
        url=url,
        title=title,
        text=text,
        word_count=word_count,
        char_count=char_count,
        fetch_method=method,
        fetched_at=datetime.now(timezone.utc),
        language=language
    )


def _detect_language(text: str) -> str:
    """
    Detects language based on CJK character ratio.
    Improved to handle mixed content (like news homepages) better.
    """
    cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    
    # If absolute count of CJK is high, it's likely Chinese regardless of boilerplate
    if cjk_count > 30:
        return "zh"
        
    total_alpha = sum(1 for c in text if c.isalpha() or '\u4e00' <= c <= '\u9fff')
    
    if total_alpha > 0 and cjk_count / total_alpha > 0.2:
        return "zh"
    return "en"


def _calculate_counts(text: str, language: str) -> Tuple[int, int]:
    char_count = len(text)
    if language == "zh":
        word_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    else:
        word_count = len(text.split())
    return word_count, char_count