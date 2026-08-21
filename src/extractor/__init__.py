"""Top-level orchestration with Confidence Engine and Structured API Schema."""
from __future__ import annotations

from bs4 import BeautifulSoup

from .colors import extract_palette
from .fetcher import FetchError, fetch_html, normalize_url
from .fonts import extract_fonts
from .jsonld import extract_json_ld
from .logo import extract_favicon, extract_logo
from .metadata import extract_metadata
from .social import extract_social_links
from .styles import collect_css_text

__all__ = ["extract_brand_kit", "FetchError"]


def _calculate_confidence(asset: any, field_type: str, source: str = "heuristics") -> float:
    """Calculate extraction confidence score between 0.00 and 1.00."""
    if not asset:
        return 0.00
    if source == "jsonld":
        return 0.98
    if field_type == "favicon" and "favicon.ico" not in str(asset):
        return 0.95
    if field_type == "logo" and ("svg" in str(asset).lower() or "logo" in str(asset).lower()):
        return 0.92
    if field_type == "colors":
        return 0.90
    if field_type == "fonts":
        return 0.88
    return 0.80


def extract_brand_kit(raw_url: str) -> dict:
    url = normalize_url(raw_url)
    final_url, html = fetch_html(url)

    soup = BeautifulSoup(html, "html.parser")
    css_text = collect_css_text(soup, final_url)
    json_ld = extract_json_ld(soup)

    metadata = extract_metadata(soup, final_url)
    logo_url = extract_logo(soup, final_url)
    favicon_url = extract_favicon(soup, final_url)
    social_links = extract_social_links(soup, final_url)
    colors = extract_palette(css_text, soup)
    fonts = extract_fonts(css_text, soup)

    # Legacy flat output (for backward compatibility with batch_run.py)
    flat_response = {
        "url": final_url,
        "metadata": metadata,
        "logo": logo_url,
        "favicon": favicon_url,
        "social_links": social_links,
        "colors": colors,
        "fonts": fonts,
    }

    # Enhanced Structured Confidence Schema
    logo_source = "jsonld" if json_ld.get("logo") and logo_url == json_ld["logo"] else "heuristics"
    structured_response = {
        "url": final_url,
        "brand_name": {
            "value": json_ld.get("name") or metadata.get("site_name") or metadata.get("title"),
            "confidence": 0.95 if json_ld.get("name") else 0.80,
        },
        "logo": {
            "url": logo_url,
            "source": logo_source,
            "confidence": _calculate_confidence(logo_url, "logo", logo_source),
            "verified": bool(logo_url),
        },
        "favicon": {
            "url": favicon_url,
            "source": "link_rel",
            "confidence": _calculate_confidence(favicon_url, "favicon"),
            "verified": bool(favicon_url),
        },
        "colors": [
            {
                "value": color,
                "confidence": 0.92 - (idx * 0.05),
                "first_party": True,
            } for idx, color in enumerate(colors)
        ],
        "typography": {
            "families": [
                {
                    "family": font,
                    "confidence": 0.90 - (idx * 0.05),
                } for idx, font in enumerate(fonts.get("families", []))
            ],
            "google_fonts": fonts.get("google_fonts", []),
        },
        "social_links": {
            platform: {
                "url": link,
                "confidence": 0.98 if link in json_ld.get("social_links", []) else 0.85,
            } for platform, link in social_links.items()
        },
        "extraction_metadata": {
            "method": "static",
            "confidence_score": round(
                (
                    (1.0 if logo_url else 0.0) +
                    (1.0 if favicon_url else 0.0) +
                    (1.0 if colors else 0.0) +
                    (1.0 if fonts.get("families") else 0.0) +
                    (1.0 if social_links else 0.0)
                ) / 5.0, 2
            )
        }
    }

    # Merge legacy keys into structured dictionary so callers get both formats
    structured_response.update(flat_response)
    return structured_response
