"""Reading a built page back: a small HTML reader over the standard
library's parser, for scripts/check_site.py and the tests.

A page is read into its elements in document order. Each element has its
tag, its attributes, its text (every text node inside it, with runs of white
space folded to one space) and the links inside it, so a check can ask for
"the paragraph marked data-kt-printables" and compare its words and its
links without matching markup with a regular expression. Script and style
contents are not text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

_VOID = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
)
_NOT_TEXT = frozenset({"script", "style"})


@dataclass
class Element:
    tag: str
    attrs: dict[str, str]
    parts: list[str] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join("".join(self.parts).split())


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[Element] = []
        self._open: list[Element] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        el = Element(tag, {k: v or "" for k, v in attrs})
        self.elements.append(el)
        if tag not in _VOID:
            self._open.append(el)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append(Element(tag, {k: v or "" for k, v in attrs}))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i].tag == tag:
                closed = self._open[i]
                del self._open[i:]
                if tag == "a" and "href" in closed.attrs:
                    for el in self._open:
                        el.links.append((closed.attrs["href"], closed.text))
                return

    def handle_data(self, data: str) -> None:
        if self._open and self._open[-1].tag in _NOT_TEXT:
            return
        for el in self._open:
            el.parts.append(data)


def read(html: str) -> list[Element]:
    """Every element of the page, in document order."""
    reader = _Reader()
    reader.feed(html)
    reader.close()
    return reader.elements


def marked(elements: list[Element], attr: str, tag: str | None = None) -> list[Element]:
    """The elements that carry the attribute `attr` (and are `tag`, if given)."""
    return [el for el in elements if attr in el.attrs and (tag is None or el.tag == tag)]


def tagged(elements: list[Element], tag: str) -> list[Element]:
    return [el for el in elements if el.tag == tag]


def meta(elements: list[Element], name: str) -> str | None:
    """The content of <meta name=...>, or None when the page has none."""
    for el in elements:
        if el.tag == "meta" and el.attrs.get("name") == name:
            return el.attrs.get("content", "")
    return None
