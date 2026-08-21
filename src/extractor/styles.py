"""Shared CSS-gathering logic used by the color and font extractors."""
from __future__ import annotations

from bs4 import BeautifulSoup

from .fetcher import FetchError, fetch_bytes, resolve

MAX_STYLESHEETS = 5
MAX_CSS_BYTES = 300_000  # cap per stylesheet so a huge bundle can't blow the Lambda timeout/memory


def collect_css_text(soup: BeautifulSoup, base_url: str) -> str:
    """Concatenate inline <style> blocks, style="" attributes, and up to
    MAX_STYLESHEETS linked stylesheets into one CSS blob for regex/parsing."""
    chunks: list[str] = []

    for style_tag in soup.find_all("style"):
        if style_tag.string:
            chunks.append(style_tag.string)

    for tag in soup.find_all(style=True):
        chunks.append("* { " + tag["style"] + " }")

    link_tags = [
        link for link in soup.find_all("link", href=True)
        if "stylesheet" in " ".join(link.get("rel", [])).lower()
    ]
    for link in link_tags[:MAX_STYLESHEETS]:
        css_url = resolve(base_url, link["href"])
        if not css_url or not css_url.startswith(("http://", "https://")):
            continue
        try:
            content, _ = fetch_bytes(css_url, referer=base_url)
        except (FetchError, Exception):
            continue
        text = content[:MAX_CSS_BYTES].decode("utf-8", errors="ignore")
        chunks.append(text)

    return "\n".join(chunks)
