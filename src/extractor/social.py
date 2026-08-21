"""Extract social media profile links from a page with JSON-LD integration and URL normalization."""
from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from .fetcher import resolve
from .jsonld import extract_json_ld

# Domain -> canonical platform name.
PLATFORM_DOMAINS = {
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "instagram.com": "instagram",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "linkedin.com": "linkedin",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "tiktok.com": "tiktok",
    "pinterest.com": "pinterest",
    "pinterest.co.uk": "pinterest",
    "github.com": "github",
    "wa.me": "whatsapp",
    "whatsapp.com": "whatsapp",
    "t.me": "telegram",
    "telegram.me": "telegram",
    "telegram.org": "telegram",
    "discord.gg": "discord",
    "discord.com": "discord",
    "snapchat.com": "snapchat",
    "reddit.com": "reddit",
    "medium.com": "medium",
    "threads.net": "threads",
    "vimeo.com": "vimeo",
    "behance.net": "behance",
    "dribbble.com": "dribbble",
    "spotify.com": "spotify",
    "twitch.tv": "twitch",
}

# Paths/query parameters indicating share widgets or post content rather than brand profile pages
SHARE_PATH_HINTS = (
    "/sharer", "/share", "/intent/", "/dialog/", "/embed", "/status/", "/p/", "/reel/", "/watch",
    "api.whatsapp.com/send", "wa.me/?text", "whatsapp.com/send", "twitter.com/share", "facebook.com/share.php",
)


def _platform_for(url: str) -> str | None:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return None
    host = host.removeprefix("www.").removeprefix("m.")
    for domain, platform in PLATFORM_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return None


def _is_share_widget(url: str) -> bool:
    lower = url.lower()
    return any(hint in lower for hint in SHARE_PATH_HINTS)


def _normalize_profile_url(url: str) -> str:
    """Clean tracking params, trailing slashes, and standardize profile URLs."""
    parsed = urlparse(url)
    clean_path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, clean_path, "", "", ""))


def extract_social_links(soup: BeautifulSoup, base_url: str) -> dict[str, str]:
    """Return {platform: url} with priority ranking:
    1. JSON-LD sameAs links (Highest precision)
    2. HTML <a> tags (Footer/Header)
    3. OpenGraph / Twitter meta tags
    """
    found: dict[str, str] = {}
    own_host = urlparse(base_url).netloc.lower().removeprefix("www.")

    # 1. High-Confidence JSON-LD sameAs Links
    json_ld = extract_json_ld(soup)
    for link in json_ld.get("social_links", []):
        platform = _platform_for(link)
        if platform and not _is_share_widget(link) and platform not in found:
            found[platform] = _normalize_profile_url(link)

    # 2. HTML <a> tags & <link>/<meta>
    candidates = []
    for tag in soup.find_all("a", href=True):
        candidates.append(tag["href"])
    for tag in soup.find_all(["link", "meta"]):
        href = tag.get("href") or (tag.get("content") if tag.get("property", "").startswith("og:") else None)
        if href:
            candidates.append(href)

    for raw_href in candidates:
        absolute = resolve(base_url, raw_href)
        if not absolute or not absolute.startswith(("http://", "https://")):
            continue
        if _is_share_widget(absolute):
            continue

        platform = _platform_for(absolute)
        if not platform or platform in found:
            continue

        link_host = urlparse(absolute).netloc.lower().removeprefix("www.")
        if link_host == own_host:
            continue

        path = urlparse(absolute).path.strip("/")
        if not path and platform != "whatsapp":
            continue

        found[platform] = _normalize_profile_url(absolute)

    return found
