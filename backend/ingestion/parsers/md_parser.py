"""Markdown / plain text → section-aware text blocks.

For Markdown: splits on headings to preserve document structure.
For plain text: splits on double newlines into paragraphs.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict


def parse_markdown(file_path: str) -> List[Dict]:
    """
    Parse a Markdown or plain text file into section blocks.

    Returns:
        List of dicts with keys: section (heading or 'text'), text
    """
    text = Path(file_path).read_text(encoding="utf-8", errors="replace")

    if file_path.endswith(".md"):
        return _split_markdown(text)
    else:
        return _split_plaintext(text)


def _split_markdown(text: str) -> List[Dict]:
    """Split on ATX headings (#, ##, ###) to preserve hierarchy."""
    heading_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))

    if not matches:
        return _split_plaintext(text)

    sections = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        heading_text = match.group(2).strip()
        body = text[start:end].strip()
        if body:
            sections.append({"section": heading_text, "text": f"{heading_text}\n\n{body}"})

    # Prepend any content before the first heading
    if matches[0].start() > 0:
        preamble = text[:matches[0].start()].strip()
        if preamble:
            sections.insert(0, {"section": "intro", "text": preamble})

    return sections


def _split_plaintext(text: str) -> List[Dict]:
    """Split on double newlines into paragraph blocks."""
    paragraphs = re.split(r"\n\n+", text)
    return [
        {"section": f"para_{i}", "text": p.strip()}
        for i, p in enumerate(paragraphs)
        if p.strip()
    ]
