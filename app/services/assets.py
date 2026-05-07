"""Asset + Clipart System.

Responsibilities:
1. Icon resolution — map icon library references (heroicons, feather, etc.)
   to inline SVG strings via CDN lookup with local cache.
2. Clipart search — find royalty-free SVG illustrations for keywords
   using the Iconify open-source icon API (no auth required).
3. Image URL validation — lightweight HEAD-request check before embedding.
4. Asset normalization — ensure all AssetSpec instances have usable sources.

All external I/O is isolated in async methods so the rest of the system
can be tested synchronously with mocked asset data.

Cache strategy:
- In-memory LRU cache (up to 512 entries) for the process lifetime.
- Assets are immutable (identified by URL/name), so no TTL is needed.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any
from urllib.parse import quote

import httpx

from app.models.deck import AssetSpec, AssetType, IconSpec


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Iconify API — free, no auth, massive icon library
_ICONIFY_API = "https://api.iconify.design"

# Supported icon library prefixes (Iconify collection IDs)
_ICON_LIBRARIES: dict[str, str] = {
    "heroicons": "heroicons",
    "feather": "feather",
    "phosphor": "ph",
    "lucide": "lucide",
    "mdi": "mdi",
    "tabler": "tabler",
}

# Fallback inline SVG for when CDN is unreachable (simple placeholder)
_FALLBACK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2">'
    '<rect x="3" y="3" width="18" height="18" rx="2"/>'
    '<line x1="3" y1="9" x2="21" y2="9"/>'
    '</svg>'
)

_REQUEST_TIMEOUT = 5.0  # seconds


# ─────────────────────────────────────────────────────────────────────────────
# SVG sanitisation (XSS prevention)
# ─────────────────────────────────────────────────────────────────────────────

_DANGEROUS_TAGS = re.compile(
    r"<\s*(script|object|embed|link|meta|iframe|base)[^>]*>",
    re.IGNORECASE | re.DOTALL,
)
_ON_ATTRS = re.compile(r"\bon\w+\s*=", re.IGNORECASE)
_JAVASCRIPT_HREF = re.compile(r'href\s*=\s*["\']?javascript:', re.IGNORECASE)
_EXTERNAL_LOAD = re.compile(r'(xlink:href|src)\s*=\s*["\']?https?://', re.IGNORECASE)


def sanitize_svg(raw: str) -> str:
    """Strip dangerous constructs from untrusted SVG content.

    Removes: script/object/embed tags, on* event attributes,
    javascript: hrefs, and external resource loads.
    """
    result = _DANGEROUS_TAGS.sub("", raw)
    result = _ON_ATTRS.sub("data-removed=", result)
    result = _JAVASCRIPT_HREF.sub('href="#"', result)
    result = _EXTERNAL_LOAD.sub(r'\1="#"', result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Icon cache (process-level, synchronous keys)
# ─────────────────────────────────────────────────────────────────────────────

# Simple dict used as a bounded cache; replaced by @lru_cache on lookup key
_icon_cache: dict[str, str] = {}
_MAX_CACHE = 512


def _cache_key(library: str, name: str) -> str:
    return f"{library}:{name}"


def _cache_get(library: str, name: str) -> str | None:
    return _icon_cache.get(_cache_key(library, name))


def _cache_set(library: str, name: str, svg: str) -> None:
    if len(_icon_cache) >= _MAX_CACHE:
        # Evict oldest entry (insertion-ordered in Python 3.7+)
        oldest = next(iter(_icon_cache))
        del _icon_cache[oldest]
    _icon_cache[_cache_key(library, name)] = svg


def clear_icon_cache() -> None:
    """Clear the in-memory icon cache (useful in tests)."""
    _icon_cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Icon resolution
# ─────────────────────────────────────────────────────────────────────────────


def _build_icon_url(library: str, name: str, color: str = "currentColor") -> str:
    """Build the Iconify SVG URL for a given icon."""
    prefix = _ICON_LIBRARIES.get(library, library)
    encoded_color = quote(color, safe="")
    return f"{_ICONIFY_API}/{prefix}/{name}.svg?color={encoded_color}"


async def fetch_icon_svg(spec: IconSpec) -> str:
    """Fetch SVG for an icon from Iconify CDN (with cache).

    Returns sanitized SVG string, or the fallback SVG on error.
    """
    cached = _cache_get(spec.library, spec.name)
    if cached is not None:
        return cached

    url = _build_icon_url(spec.library, spec.name, spec.color)
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            svg = sanitize_svg(response.text)
    except Exception:
        svg = _FALLBACK_SVG

    _cache_set(spec.library, spec.name, svg)
    return svg


def resolve_icon_url(spec: IconSpec) -> str:
    """Return the CDN URL for an icon without fetching it.

    Used by HTML renderer to emit <img src="..."> or <use href="...">.
    """
    return _build_icon_url(spec.library, spec.name, spec.color)


# ─────────────────────────────────────────────────────────────────────────────
# Clipart / illustration search
# ─────────────────────────────────────────────────────────────────────────────


async def search_clipart(query: str, limit: int = 6) -> list[AssetSpec]:
    """Search for SVG illustrations matching a keyword.

    Uses Iconify search API to find relevant icons/illustrations.
    Returns a list of AssetSpec (type=SVG) with CDN source URLs.

    Falls back to an empty list on network failure (non-fatal).
    """
    limit = min(limit, 20)
    url = f"{_ICONIFY_API}/search?query={quote(query)}&limit={limit}&category=Logos,Illustrations"
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
    except Exception:
        return []

    icons: list[str] = data.get("icons", [])
    results: list[AssetSpec] = []
    for icon_id in icons[:limit]:
        # icon_id format: "prefix:name"
        parts = icon_id.split(":", 1)
        if len(parts) != 2:
            continue
        prefix, name = parts
        results.append(AssetSpec(
            asset_type=AssetType.SVG,
            source=f"{_ICONIFY_API}/{prefix}/{name}.svg",
            alt_text=f"{name} illustration",
        ))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Image URL validation
# ─────────────────────────────────────────────────────────────────────────────


async def validate_image_url(url: str) -> bool:
    """Return True if the URL responds with a 2xx status (HEAD request).

    Non-fatal: returns False on timeout or network error.
    Rejects non-http(s) schemes and URLs longer than 2048 chars.
    """
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return False
    if len(url) > 2048:
        return False
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.head(url, follow_redirects=True)
            return response.status_code < 400
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Asset normalization
# ─────────────────────────────────────────────────────────────────────────────


def normalize_asset(asset: AssetSpec) -> AssetSpec:
    """Normalize an AssetSpec: infer type from source if not explicit.

    Does not make network calls — purely structural normalization.
    """
    source = asset.source.strip()

    # Detect inline SVG
    if source.lstrip().startswith("<svg"):
        return asset.model_copy(update={"asset_type": AssetType.SVG, "source": source})

    # Detect icon library reference (e.g. "heroicons:star")
    if re.match(r"^[a-z]+:[a-z0-9_-]+$", source):
        return asset.model_copy(update={"asset_type": AssetType.ICON, "source": source})

    # Detect CDN URL with .svg extension
    if source.lower().endswith(".svg"):
        return asset.model_copy(update={"asset_type": AssetType.SVG})

    return asset
