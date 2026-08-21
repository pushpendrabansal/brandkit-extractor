"""HTTP fetching helpers with multi-tier fallback (requests -> curl_cffi when available) and challenge detection."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import requests

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    cffi_requests = None
    HAS_CURL_CFFI = False

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

TIMEOUT = 8  # seconds per request

CHALLENGE_MARKERS = (
    "just a moment",
    "checking your browser",
    "cf-chl",
    "cf_chl_opt",
    "attention required! | cloudflare",
    "please verify you are a human",
    "captcha-delivery.com",
    "perimeterx",
    "__cf_chl_rt_tk",
    "ddos protection by",
    "access denied",
    "request unsuccessful. incapsula",
    "your request has been blocked",
    "client challenge",
    "verifying device",
)


class FetchError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def looks_like_challenge_page(html: str) -> bool:
    """Detect bot-challenge/WAF pages that return HTTP 200 with non-content HTML."""
    title_match = _TITLE_RE.search(html)
    if title_match:
        title = title_match.group(1).lower()
        if any(marker in title for marker in CHALLENGE_MARKERS):
            return True

    lower = html.lower()
    if len(html) < 10000:
        if any(marker in lower for marker in CHALLENGE_MARKERS):
            return True

    return False


def normalize_url(url: str) -> str:
    url = url.strip()
    if not urlparse(url).scheme:
        url = "https://" + url
    return url


def fetch_html(url: str) -> tuple[str, str]:
    """Fetch a page and return (final_url, html_text) using requests with curl_cffi impersonation fallback."""
    last_error = None

    # Tier 1: curl_cffi Browser Impersonation (if installed)
    if HAS_CURL_CFFI:
        try:
            resp = cffi_requests.get(
                url, headers=DEFAULT_HEADERS, timeout=TIMEOUT, impersonate="chrome120", follow_redirects=True
            )
            if resp.status_code < 400 and not looks_like_challenge_page(resp.text):
                return resp.url, resp.text
            if resp.status_code >= 400:
                last_error = f"curl_cffi returned HTTP {resp.status_code}"
        except Exception as exc:
            last_error = f"curl_cffi failed: {exc}"

    # Tier 2: Standard Python requests fallback
    try:
        resp = requests.get(
            url, headers=DEFAULT_HEADERS, timeout=TIMEOUT, allow_redirects=True
        )
    except requests.exceptions.RequestException as exc:
        raise FetchError(f"Could not reach {url}: {exc}") from exc

    if resp.status_code >= 400:
        raise FetchError(f"{url} returned HTTP {resp.status_code}", resp.status_code)

    resp.encoding = resp.encoding or "utf-8"

    if looks_like_challenge_page(resp.text):
        raise FetchError(f"{url} returned a bot-challenge/interstitial page, not real content")

    return resp.url, resp.text


def fetch_bytes(url: str, referer: str | None = None) -> tuple[bytes, str]:
    """Fetch binary content (images, CSS). Returns (content, content_type)."""
    headers = dict(DEFAULT_HEADERS)
    if referer:
        headers["Referer"] = referer
    resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "")


def resolve(base_url: str, maybe_relative: str | None) -> str | None:
    if not maybe_relative:
        return None
    maybe_relative = maybe_relative.strip()
    if not maybe_relative or maybe_relative.startswith("data:"):
        return maybe_relative or None
    return urljoin(base_url, maybe_relative)
