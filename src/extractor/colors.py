"""Extract a candidate brand color palette with CSS variable resolution and framework noise filtering."""
from __future__ import annotations

import re
from collections import Counter
from bs4 import BeautifulSoup

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
RGB_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*[\d.]+\s*)?\)")
CSS_VAR_DEF_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;}]+)")
CSS_VAR_REF_RE = re.compile(r"var\(\s*(--[\w-]+)(?:\s*,\s*([^)]+))?\s*\)")

# Generic noise colors (black/white/grays/transparent defaults)
NOISE_HEXES = {
    "#fff", "#ffffff", "#000", "#000000", "#fafafa", "#f5f5f5", "#f0f0f0",
    "#eee", "#eeeeee", "#ddd", "#dddddd", "#ccc", "#cccccc", "#111111", "#222222", "#333333",
}


def _normalize_hex(value: str) -> str:
    value = value.lower()
    if len(value) == 4:  # #abc -> #aabbcc
        value = "#" + "".join(ch * 2 for ch in value[1:])
    return value


def _rgb_to_hex(r: str, g: str, b: str) -> str:
    return "#{:02x}{:02x}{:02x}".format(int(r), int(g), int(b))


def resolve_css_variables(css_text: str) -> str:
    """Extract CSS custom properties (--brand-primary: #635bff) and recursively replace var(--*) usages."""
    var_map: dict[str, str] = {}
    
    # Pass 1: Gather variable definitions
    for match in CSS_VAR_DEF_RE.finditer(css_text):
        var_name = match.group(1).strip()
        var_val = match.group(2).strip()
        var_map[var_name] = var_val

    # Pass 2: Substitute var() references
    def replace_var(match):
        vname = match.group(1).strip()
        fallback = match.group(2).strip() if match.group(2) else ""
        return var_map.get(vname, fallback or match.group(0))

    resolved_css = css_text
    for _ in range(3):  # up to 3 recursive resolution passes
        if "var(" not in resolved_css:
            break
        resolved_css = CSS_VAR_REF_RE.sub(replace_var, resolved_css)

    return resolved_css


def extract_theme_color_meta(soup: BeautifulSoup) -> str | None:
    tag = soup.find("meta", attrs={"name": "theme-color"})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def extract_palette(css_text: str, soup: BeautifulSoup, top_n: int = 6) -> list[str]:
    """Extract brand color palette with variable expansion and semantic weighting."""
    resolved_css = resolve_css_variables(css_text)
    counts: Counter[str] = Counter()

    for match in HEX_RE.finditer(resolved_css):
        hexval = _normalize_hex(match.group(0))
        if hexval not in NOISE_HEXES:
            counts[hexval] += 1

    for match in RGB_RE.finditer(resolved_css):
        hexval = _rgb_to_hex(*match.groups()[:3])
        if hexval not in NOISE_HEXES:
            counts[hexval] += 1

    palette = [color for color, _ in counts.most_common(top_n)]

    # Theme-color meta tag boost
    theme_color = extract_theme_color_meta(soup)
    if theme_color:
        norm = _normalize_hex(theme_color) if theme_color.startswith("#") else theme_color.lower()
        if norm not in NOISE_HEXES:
            if norm in palette:
                palette.remove(norm)
            palette.insert(0, norm)

    return palette[:top_n]
