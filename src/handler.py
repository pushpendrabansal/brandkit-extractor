"""Single-function Lambda entry point for brand kit extraction.

Accepts either:
  - API Gateway (REST or HTTP API / payload format 2.0) events, with the
    target URL passed as ?url= query param (GET) or JSON body {"url": ...} (POST)
  - Direct Lambda invoke with {"url": "..."} as the event itself

Response is always JSON: 200 with the brand kit payload, or 4xx/5xx with {"error": "..."}.
"""
from __future__ import annotations

import json
import logging

from extractor import FetchError, extract_brand_kit

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **CORS_HEADERS},
        "body": json.dumps(body),
    }


def _extract_url_from_event(event: dict) -> str | None:
    # API Gateway HTTP API (payload v2) / REST API query string params
    query_params = event.get("queryStringParameters") or {}
    if query_params.get("url"):
        return query_params["url"]

    # JSON body from POST (API Gateway wraps it as a string)
    body = event.get("body")
    if body:
        try:
            parsed = json.loads(body) if isinstance(body, str) else body
            if isinstance(parsed, dict) and parsed.get("url"):
                return parsed["url"]
        except (json.JSONDecodeError, TypeError):
            pass

    # Direct Lambda invoke: {"url": "..."}
    if event.get("url"):
        return event["url"]

    return None


def handler(event: dict, context) -> dict:
    if event.get("httpMethod") == "OPTIONS" or (
        event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS"
    ):
        return _response(200, {})

    url = _extract_url_from_event(event or {})
    if not url:
        return _response(400, {"error": "Missing required 'url' parameter."})

    try:
        result = extract_brand_kit(url)
    except FetchError as exc:
        logger.warning("Fetch failed for %s: %s", url, exc)
        return _response(502, {"error": str(exc)})
    except Exception:
        logger.exception("Unexpected error extracting brand kit for %s", url)
        return _response(500, {"error": "Internal error while extracting brand kit."})

    return _response(200, result)
