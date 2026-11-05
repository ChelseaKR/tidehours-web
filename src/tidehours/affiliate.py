"""Amazon affiliate links on the English king-tide page (docs/DECISIONS.md 0016).

Off unless an Associates tracking ID is configured (`Config.amazon_tag`,
`--amazon-tag`, the repo variable AMAZON_ASSOCIATE_TAG). Off, the build is
the same as before this module existed: no link, no disclosure, and the
privacy, terms and about pages unchanged. On, `/king-tides/` (English only)
carries four plain category-search links after its method section, with
Amazon's required disclosure next to them.

The links are searches, never named products: no brand, price, rating or
image (Amazon's Program Policies allow prices only from its product APIs).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

# An Associates tracking ID: lowercase letters, digits and hyphens, ending in
# the US store's "-2N" suffix (e.g. tidehours-20). fullmatch, so a trailing
# space or newline is refused.
TAG_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*-2[0-9]")
SEARCH_URL = "https://www.amazon.com/s"
# Amazon Associates Operating Agreement, Section 5, byte for byte.
DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."
REL = "sponsored nofollow noopener"
PAGE = "king-tides/"
MAX_LINKS = 4
COPY = Path(__file__).parent / "copy" / "affiliate.json"


def valid_tag(tag: str) -> bool:
    return TAG_PATTERN.fullmatch(tag) is not None


def amazon_search_url(terms: str, tag: str) -> str:
    """A plain tagged Amazon search: no redirect, shortener or script."""
    if not valid_tag(tag):
        raise ValueError(f"not an Associates tracking ID: {tag!r}")
    if not terms.strip():
        raise ValueError("empty search terms")
    return f"{SEARCH_URL}?{urlencode({'k': terms, 'tag': tag})}"


@dataclass(frozen=True)
class Link:
    label: str
    href: str


def block(tag: str) -> dict[str, Any] | None:
    """The king-tide page's affiliate block, or None when the switch is off."""
    if not tag:
        return None
    copy: dict[str, Any] = json.loads(COPY.read_text(encoding="utf-8"))
    links = [Link(item["label"], amazon_search_url(item["terms"], tag)) for item in copy["links"]]
    if not 0 < len(links) <= MAX_LINKS:
        raise ValueError(f"affiliate copy lists {len(links)} links; 1 to {MAX_LINKS} allowed")
    return {"text": copy, "links": links, "disclosure": DISCLOSURE, "rel": REL}
