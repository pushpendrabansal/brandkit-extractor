"""Extract logo and favicon candidates from a page using candidate scoring."""
from __future__ import annotations

import re
from bs4 import BeautifulSoup
import requests

from .fetcher import DEFAULT_HEADERS, TIMEOUT, resolve
from .jsonld import extract_json_ld

LOGO_HINT_RE = re.compile(r"(logo|brand|wordmark|masthead|site-logo|header-logo|navbar-logo)", re.IGNORECASE)
FAVICON_RELS = ("icon", "shortcut icon", "apple-touch-icon", "apple-touch-icon-precomposed", "mask-icon")
CSS_BG_URL_RE = re.compile(r"url\s*\(\s*['\"]?([^'\"\)]+)['\"]?\s*\)", re.IGNORECASE)


def _in_header_landmark(tag) -> bool:
    parent = tag.parent
    depth = 0
    while parent is not None and depth < 6:
        name = getattr(parent, "name", None)
        blob = " ".join(str(parent.get(attr, "")) for attr in ("id", "class", "role"))
        if name in ("header", "nav") or "header" in blob.lower() or "navbar" in blob.lower():
            return True
        parent = parent.parent
        depth += 1
    return False


def _score_img(tag) -> int:
    score = 0
    blob = " ".join(
        str(tag.get(attr, "")) for attr in ("id", "class", "alt", "src", "title", "aria-label")
    )
    
    if LOGO_HINT_RE.search(blob):
        score += 25
    
    if tag.get("alt") and "logo" in tag["alt"].lower():
        score += 20

    if _in_header_landmark(tag):
        score += 20
    else:
        score -= 10

    # Home link wrapper boost (<a href="/">)
    anchor = tag.find_parent("a", href=True)
    if anchor and anchor["href"].strip() in ("/", "", "#", base_url_home_path(tag)):
        score += 20

    return score


def base_url_home_path(tag) -> str:
    return "/"


def extract_logo(soup: BeautifulSoup, base_url: str) -> str | None:
    """Multi-tiered logo candidate scoring engine.
    
    Order of precedence / scoring:
    Tier 1 (Highest): JSON-LD Organization.logo / Brand.logo
    Tier 2: <img> tags with explicit logo hints + header positioning + home link wrapper
    Tier 3: <svg> elements with logo attributes or <use> references
    Tier 4: CSS background-image style rules matching logo classes/ids
    """
    # Tier 1: JSON-LD Structured Data
    json_ld = extract_json_ld(soup)
    if json_ld.get("logo"):
        resolved_jsonld_logo = resolve(base_url, json_ld["logo"])
        if resolved_jsonld_logo:
            return resolved_jsonld_logo

    candidates: list[tuple[int, str]] = []

    # Tier 2: <img> tags
    for img in soup.find_all("img", src=True):
        score = _score_img(img)
        if score > 0:
            candidates.append((score, img["src"]))

    # Tier 3: <svg> elements
    for svg in soup.find_all("svg"):
        blob = " ".join(str(svg.get(attr, "")) for attr in ("id", "class", "aria-label", "data-icon"))
        if LOGO_HINT_RE.search(blob):
            score = 15
            if _in_header_landmark(svg):
                score += 15
            anchor = svg.find_parent("a", href=True)
            if anchor and anchor["href"].strip() in ("/", "", "#"):
                score += 15
            
            use = svg.find("use")
            href = use.get("href") or use.get("xlink:href") if use else None
            if href:
                candidates.append((score, href))

    # Tier 4: CSS background-images (e.g. .logo { background-image: url('/logo.svg') })
    for tag in soup.find_all(True, style=True):
        blob = " ".join(str(tag.get(attr, "")) for attr in ("id", "class"))
        if LOGO_HINT_RE.search(blob):
            style = tag["style"]
            match = CSS_BG_URL_RE.search(style)
            if match:
                candidates.append((25 if _in_header_landmark(tag) else 10, match.group(1)))

    # Tier 4b: Check inline <style> blocks for .logo / #logo rules
    for style_tag in soup.find_all("style"):
        if style_tag.string:
            for rule_match in re.finditer(r"([.#][\w-]*logo[\w-]*)\s*\{[^}]*background(?:-image)?\s*:\s*url\s*\(\s*['\"]?([^'\"\)]+)['\"]?\s*\)", style_tag.string, re.IGNORECASE):
                candidates.append((20, rule_match.group(2)))

    if not candidates:
        return None

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return resolve(base_url, candidates[0][1])


def extract_favicon(soup: BeautifulSoup, base_url: str) -> str | None:
    best = None
    best_size = -1
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel", [])).lower()
        if not any(r in rel for r in FAVICON_RELS):
            continue
        sizes = link.get("sizes", "")
        size_num = 0
        match = re.search(r"(\d+)x\d+", sizes)
        if match:
            size_num = int(match.group(1))
        if size_num >= best_size:
            best_size = size_num
            best = link["href"]

    if best:
        return resolve(base_url, best)

    # Fallback to verified /favicon.ico
    fallback = resolve(base_url, "/favicon.ico")
    if fallback and _url_exists(fallback):
        return fallback
    return None


def _url_exists(url: str) -> bool:
    try:
        resp = requests.head(
            url, headers=DEFAULT_HEADERS, timeout=TIMEOUT, allow_redirects=True
        )
        if resp.status_code == 405:  # retry with GET if HEAD is forbidden
            resp = requests.get(
                url, headers=DEFAULT_HEADERS, timeout=TIMEOUT, stream=True
            )
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False
