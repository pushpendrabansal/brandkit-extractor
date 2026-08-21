"""Parse application/ld+json blocks to extract Organization / Brand logo and sameAs social profile links."""
from __future__ import annotations

import json
from bs4 import BeautifulSoup


def extract_json_ld(soup: BeautifulSoup) -> dict:
    """Extract structured data from JSON-LD scripts.
    
    Returns:
        {
            "logo": str | None,
            "social_links": list[str],
            "name": str | None,
        }
    """
    results = {
        "logo": None,
        "social_links": [],
        "name": None,
    }

    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            
            # Recursively check @graph array if present
            if "@graph" in item and isinstance(item["@graph"], list):
                items.extend(item["@graph"])

            item_type = item.get("@type", "")
            if isinstance(item_type, list):
                item_types = [str(t).lower() for t in item_type]
            else:
                item_types = [str(item_type).lower()]

            if any(t in ("organization", "brand", "corporation", "localbusiness", "website") for t in item_types):
                # Extract Logo
                logo = item.get("logo")
                if isinstance(logo, dict):
                    logo = logo.get("url") or logo.get("contentUrl")
                if isinstance(logo, str) and logo.strip() and not results["logo"]:
                    results["logo"] = logo.strip()

                # Extract SameAs (Social Profile Links)
                same_as = item.get("sameAs")
                if isinstance(same_as, str):
                    same_as = [same_as]
                if isinstance(same_as, list):
                    for link in same_as:
                        if isinstance(link, str) and link.strip() and link not in results["social_links"]:
                            results["social_links"].append(link.strip())

                # Extract Name
                name = item.get("name")
                if isinstance(name, str) and name.strip() and not results["name"]:
                    results["name"] = name.strip()

    return results
