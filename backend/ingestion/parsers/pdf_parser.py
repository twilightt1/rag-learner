"""PDF → plain text using pymupdf.

Returns a list of page dicts: {page_num, text}
Strips headers/footers heuristically by ignoring lines repeated across pages.
"""
from pathlib import Path
from typing import List, Dict
from collections import Counter
import re


def parse_pdf(file_path: str) -> List[Dict]:
    """
    Parse a PDF file into per-page text blocks.

    Returns:
        List of dicts with keys: page_num (1-based), text
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        raise RuntimeError("pymupdf not installed. Run: pip install pymupdf")

    doc = fitz.open(file_path)
    pages = []

    raw_pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        raw_pages.append({"page_num": i + 1, "text": text})

    # Detect repeated lines (likely headers/footers) across 3+ pages
    line_counts: Counter = Counter()
    for p in raw_pages:
        for line in p["text"].splitlines():
            stripped = line.strip()
            if stripped:
                line_counts[stripped] += 1

    threshold = max(3, len(raw_pages) * 0.4)
    repeated = {line for line, count in line_counts.items() if count >= threshold}

    for p in raw_pages:
        clean_lines = [
            line for line in p["text"].splitlines()
            if line.strip() not in repeated
        ]
        clean_text = "\n".join(clean_lines).strip()
        # Collapse excessive blank lines
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)
        if clean_text:
            pages.append({"page_num": p["page_num"], "text": clean_text})

    doc.close()
    return pages
