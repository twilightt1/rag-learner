"""Web URL → clean text using Playwright (async).

Handles JS-rendered pages. Strips nav, footer, ads heuristically.
Returns list of blocks compatible with the chunker.
"""
from __future__ import annotations

import re
from typing import List, Dict


async def parse_url(url: str) -> List[Dict]:
    """
    Crawl a URL and extract readable text content.

    Returns:
        List of dicts with keys: section, text
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("playwright not installed. Run: pip install playwright && playwright install chromium")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)  # allow JS to settle

            # Extract title
            title = await page.title()

            # Remove clutter elements
            await page.evaluate("""
                const selectors = [
                    'nav', 'header', 'footer', 'aside',
                    '[class*="sidebar"]', '[class*="menu"]',
                    '[class*="cookie"]', '[class*="popup"]',
                    '[class*="banner"]', '[class*="ad"]',
                    'script', 'style', 'noscript'
                ];
                selectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => el.remove());
                });
            """)

            # Try to find main content area
            content = await page.evaluate("""
                const candidates = ['main', 'article', '[role="main"]', '#content', '.content', 'body'];
                for (const sel of candidates) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText && el.innerText.trim().length > 200) {
                        return el.innerText;
                    }
                }
                return document.body.innerText;
            """)

        finally:
            await browser.close()

    if not content:
        raise ValueError(f"No readable content found at {url}")

    # Clean up extracted text
    clean = _clean_text(content)
    blocks = _split_into_blocks(clean, title)
    return blocks


def _clean_text(text: str) -> str:
    """Normalise whitespace and strip junk lines."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip very short lines (likely nav items, single words)
        if len(stripped) < 3:
            continue
        cleaned.append(stripped)
    text = "\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_into_blocks(text: str, title: str) -> List[Dict]:
    """Split cleaned text into logical blocks."""
    blocks = []

    # Add title as first block
    if title:
        blocks.append({"section": "title", "text": title})

    # Split on double newlines
    paragraphs = re.split(r"\n\n+", text)
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if len(para) > 50:  # ignore tiny fragments
            blocks.append({"section": f"section_{i}", "text": para})

    return blocks
