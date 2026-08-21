"""Extract page/site metadata: title, description, OpenGraph info."""
from __future__ import annotations

from bs4 import BeautifulSoup

from .fetcher import resolve


def _meta_content(soup: BeautifulSoup, **attrs) -> str | None:
    tag = soup.find("meta", attrs=attrs)
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def extract_metadata(soup: BeautifulSoup, base_url: str) -> dict:
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    og_title = _meta_content(soup, property="og:title")

    description = _meta_content(soup, name="description") or _meta_content(
        soup, property="og:description"
    )

    og_image = _meta_content(soup, property="og:image") or _meta_content(
        soup, name="twitter:image"
    )
    og_site_name = _meta_content(soup, property="og:site_name")

    return {
        "title": og_title or title,
        "description": description,
        "site_name": og_site_name,
        "og_image": resolve(base_url, og_image) if og_image else None,
    }
