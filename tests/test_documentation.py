from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
PRIMARY_DOCS = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "docs" / "README.md",
    PROJECT_ROOT / "docs" / "architecture.md",
    PROJECT_ROOT / "docs" / "usage.md",
    PROJECT_ROOT / "docs" / "technology-guide.md",
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_documentation_index_links_primary_guides() -> None:
    index = (PROJECT_ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    assert "(architecture.md)" in index
    assert "(usage.md)" in index
    assert "(technology-guide.md)" in index


def test_primary_documentation_links_resolve() -> None:
    missing: list[str] = []
    for document in PRIMARY_DOCS:
        text = document.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative_path = target.split("#", maxsplit=1)[0]
            if relative_path and not (document.parent / relative_path).exists():
                missing.append(f"{document.relative_to(PROJECT_ROOT)} -> {target}")

    assert missing == []
