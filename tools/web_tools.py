"""
Web & Browser Automation Tools.
Supports live DuckDuckGo web searches, webpage content scraping,
and default browser URL navigation.
"""

from __future__ import annotations
import webbrowser
import logging
from typing import Optional, List, Dict, Any
try:
    import httpx
except ImportError:
    httpx = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from config import RiskLevel
from core.security import RiskLevel

logger = logging.getLogger("JARVIS.Tools.Web")


def web_search(query: str, max_results: int = 5) -> str:
    """
    Performs a live web search using DuckDuckGo and returns top results with titles, snippets, and links.
    """
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
            for r in raw_results:
                title = r.get("title", "")
                snippet = r.get("body", "")
                link = r.get("href", "")
                results.append(f"• **{title}**\n  {snippet}\n  Link: {link}")

        if not results:
            return f"No search results found for query: '{query}'."

        return f"Web Search Results for '{query}':\n\n" + "\n\n".join(results)
    except Exception as e:
        logger.error(f"Search failure: {e}")
        return f"Failed to execute web search: {str(e)}"


def open_browser_url(url: str) -> str:
    """
    Opens the specified website URL in the user's default desktop web browser.
    """
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = "https://" + clean_url

    try:
        webbrowser.open(clean_url)
        return f"Opened URL in web browser: {clean_url}"
    except Exception as e:
        return f"Failed to open browser URL: {str(e)}"


def scrape_webpage(url: str, max_chars: int = 3000) -> str:
    """
    Fetches a webpage, strips HTML markup/ads/scripts, and extracts the readable body text.
    """
    if not httpx or not BeautifulSoup:
        return "httpx or beautifulsoup4 is not installed. Run: pip install httpx beautifulsoup4"
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = "https://" + clean_url

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(clean_url)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts, style sheets, meta tags, and header/footer boilerplates
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()

        # Extract text
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_content = "\n".join(lines)[:max_chars]

        title = soup.title.string.strip() if soup.title else "Webpage"
        return f"[Title: {title}]\nSource: {clean_url}\n\nContent:\n{clean_content}..."
    except Exception as e:
        return f"Failed to extract content from '{url}': {str(e)}"


# Register with Tool Registry
from tools import registry

registry.register("web_search", "Performs real-time internet search for current facts and news.", RiskLevel.READ_ONLY)(web_search)
registry.register("open_browser_url", "Opens website URL in the user's default browser.", RiskLevel.SAFE_EXECUTION)(open_browser_url)
registry.register("scrape_webpage", "Fetches and reads the text contents of a webpage URL.", RiskLevel.READ_ONLY)(scrape_webpage)
