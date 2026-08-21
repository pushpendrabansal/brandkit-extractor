"""Extract typography info with CSS variable resolution, @font-face ranking, and framework filtering."""
from __future__ import annotations

import re
from bs4 import BeautifulSoup
from .colors import resolve_css_variables

FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;}]+)", re.IGNORECASE)
FONT_FACE_RE = re.compile(r"@font-face\s*\{[^}]*font-family\s*:\s*['\"]?([^'\";\}]+)['\"]?", re.IGNORECASE)
GENERIC_FONT_KEYWORDS = {
    "serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui",
    "-apple-system", "blinkmacsystemfont", "inherit", "initial", "unset",
    "arial", "helvetica", "verdana", "georgia", "times new roman", "times",
}


def _clean_family_list(raw: str) -> list[str]:
    names = []
    for part in raw.split(","):
        name = part.strip().strip("'\"")
        if not name or name.lower() in GENERIC_FONT_KEYWORDS or name.startswith("var("):
            continue
        names.append(name)
    return names


def extract_fonts(css_text: str, soup: BeautifulSoup, top_n: int = 5) -> dict:
    resolved_css = resolve_css_variables(css_text)
    seen: dict[str, int] = {}

    # Boost @font-face declarations (+50 weight)
    for match in FONT_FACE_RE.finditer(resolved_css):
        for name in _clean_family_list(match.group(1)):
            seen[name] = seen.get(name, 0) + 50

    # Normal font-family rules
    for match in FONT_FAMILY_RE.finditer(resolved_css):
        for name in _clean_family_list(match.group(1)):
            seen[name] = seen.get(name, 0) + 1

    ranked = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)
    families = [name for name, _ in ranked[:top_n]]

    # Google Fonts
    google_fonts = []
    for link in soup.find_all("link", href=True):
        href = link["href"]
        if "fonts.googleapis.com" in href:
            match = re.search(r"family=([^&]+)", href)
            if match:
                for fam in match.group(1).split("|"):
                    fam_name = fam.split(":")[0].replace("+", " ")
                    if fam_name not in google_fonts and fam_name.lower() not in GENERIC_FONT_KEYWORDS:
                        google_fonts.append(fam_name)

    return {"families": families, "google_fonts": google_fonts}
