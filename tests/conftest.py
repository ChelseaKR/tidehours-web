"""Shared test setup.

The tide gifts page (docs/DECISIONS.md 0041) lists the moon calendars and
the printed tide tables in every build, whatever its states, so with the
committed gift list every test build would carry the page and its footer
link. The tests that are about other things build without it: for the
whole session, `gifts.load()` with no path reads an empty list.
tests/test_gifts.py names the committed list with `--gifts` wherever it
means the site as published, as tests/test_site.py names empty calendar and
poster lists so that its tests stay about the site without them."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tidehours import gifts


@pytest.fixture(scope="session", autouse=True)
def no_gifts_unless_named(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    empty = tmp_path_factory.mktemp("no-gifts") / "gifts.json"
    empty.write_text('{"gifts": []}', encoding="utf-8")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(gifts, "LIST", empty)
        yield empty
