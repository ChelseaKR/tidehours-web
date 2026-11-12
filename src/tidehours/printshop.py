"""A link to the Tide Hours print shop on Etsy (docs/DECISIONS.md 0029).

Off unless a shop address is configured (`Config.print_shop_url`,
`--print-shop-url`, the repo variable PRINT_SHOP_URL). Off, the build has no
trace of it: no link, no section, and the privacy and terms pages unchanged.
On, the About page and the English king-tide page each carry one sentence
with one plain link to the shop, the privacy page says where the link goes,
and the terms page names Etsy among the trademarks.

The shop is Tide Hours' own, so this is not an affiliate link: no tag, no
tracking parameter, no click event, and no price or claim in the sentence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# An Etsy shop's own address, nothing else: no listing, search, query string
# or tracking parameter. fullmatch, so a trailing space or newline is refused.
URL_PATTERN = re.compile(r"https://www\.etsy\.com/shop/[A-Za-z0-9]{4,20}")
REL = "noopener"
# The pages that carry the link, as paths in the built site.
PAGES = ("about/", "king-tides/")
# The pages that may name Etsy in words without linking to it.
MENTION_PAGES = ("privacy/", "terms/")
COPY = Path(__file__).parent / "copy" / "print_shop.json"


def valid_url(url: str) -> bool:
    return URL_PATTERN.fullmatch(url) is not None


def block(url: str) -> dict[str, Any] | None:
    """What the templates need for the link, or None when the switch is off."""
    if not url:
        return None
    if not valid_url(url):
        raise ValueError(f"not an Etsy shop address: {url!r}")
    text: dict[str, Any] = json.loads(COPY.read_text(encoding="utf-8"))
    return {"url": url, "rel": REL, "text": text}
