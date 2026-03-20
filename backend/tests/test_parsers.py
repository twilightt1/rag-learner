from __future__ import annotations

import pytest

from backend.ingestion.parsers.pdf_parser import parse_pdf
from backend.ingestion.parsers.md_parser import parse_markdown
from backend.ingestion.parsers.code_parser import parse_code
from backend.ingestion.parsers.url_parser import parse_url


# --- PDF Parser Tests ---

def test_pdf_extracts_text(sample_pdf):
    """PDF parser extracts text content from a simple PDF."""
    pages = parse_pdf(str(sample_pdf))
    assert len(pages) >= 1
    assert "machine learning" in pages[0]["text"].lower()
    assert pages[0]["page_num"] == 1


def test_pdf_skips_blank_pages(tmp_path):
    """Blank pages are filtered out."""
    try:
        from fpdf import FPDF
    except ImportError:
        pytest.skip("fpdf2 not installed")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Page 1 has content")
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    # Page 2 is blank (no text)
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Page 3 has content")

    path = tmp_path / "blank_pages.pdf"
    pdf.output(str(path))

    pages = parse_pdf(str(path))
    texts = [p["text"].strip() for p in pages]
    assert all(texts)
    assert len(pages) == 2


def test_pdf_page_numbers_start_at_1(sample_pdf):
    """Page numbers are 1-indexed."""
    pages = parse_pdf(str(sample_pdf))
    assert pages[0]["page_num"] == 1


def test_pdf_removes_repeated_headers_footers(tmp_path):
    """Repeated lines across pages (headers/footers) are removed."""
    try:
        from fpdf import FPDF
    except ImportError:
        pytest.skip("fpdf2 not installed")

    pdf = FPDF()
    # Add 5 pages with a repeated footer
    for i in range(1, 6):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, f"Chapter {i} - Content here")
        pdf.set_y(-15)
        pdf.cell(0, 10, "Confidential", align="C")

    path = tmp_path / "header_footer.pdf"
    pdf.output(str(path))

    pages = parse_pdf(str(path))
    # "Confidential" should be removed from all pages
    for page in pages:
        assert "Confidential" not in page["text"]


# --- Markdown Parser Tests ---

def test_md_preserves_headings(sample_md):
    """Markdown parser preserves heading structure."""
    text = parse_markdown(str(sample_md))
    assert "# Introduction" in text
    assert "## Backpropagation" in text


def test_md_extracts_paragraph_text(sample_md):
    """Markdown parser extracts regular text content."""
    text = parse_markdown(str(sample_md))
    assert "neural networks" in text
    assert "Gradients flow backwards" in text


def test_md_handles_empty_file(tmp_path):
    """Empty markdown file returns empty string."""
    path = tmp_path / "empty.md"
    path.write_text("", encoding="utf-8")
    text = parse_markdown(str(path))
    assert text == ""


# --- Code Parser Tests ---

def test_code_parser_extracts_functions(sample_py):
    """Code parser extracts function definitions."""
    blocks = parse_code(str(sample_py))
    func_names = [b.get("metadata", {}).get("function_name") for b in blocks if b.get("metadata")]
    assert "add" in func_names


def test_code_parser_extracts_classes(sample_py):
    """Code parser extracts class definitions."""
    blocks = parse_code(str(sample_py))
    class_names = [b.get("metadata", {}).get("class_name") for b in blocks if b.get("metadata")]
    assert "Calculator" in class_names


def test_code_parser_handles_multiple_functions(sample_py):
    """All functions are extracted."""
    blocks = parse_code(str(sample_py))
    assert len(blocks) >= 2


def test_code_parser_javascript(sample_js):
    """Code parser handles JavaScript files."""
    blocks = parse_code(str(sample_js))
    func_names = [b.get("metadata", {}).get("function_name") for b in blocks if b.get("metadata")]
    assert "greet" in func_names


def test_code_parser_typescript(sample_ts):
    """Code parser handles TypeScript files."""
    blocks = parse_code(str(sample_ts))
    func_names = [b.get("metadata", {}).get("function_name") for b in blocks if b.get("metadata")]
    assert "greet" in func_names


def test_code_parser_unsupported_language(tmp_path):
    """Unsupported file types raise appropriate error."""
    path = tmp_path / "file.unknown"
    path.write_text("some content", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Unsupported language"):
        parse_code(str(path))


# --- URL Parser Tests ---

@pytest.mark.asyncio
async def test_url_parser_returns_blocks(mocker):
    """URL parser extracts page content."""
    from backend.ingestion.parsers.url_parser import parse_url

    # Mock Playwright
    mock_page = mocker.AsyncMock()
    mock_page.evaluate.return_value = {
        "title": "Test Page",
        "blocks": [
            {"type": "heading", "text": "Main Title"},
            {"type": "paragraph", "text": "This is test content."}
        ]
    }

    mock_browser = mocker.AsyncMock()
    mock_browser.new_page.return_value = mock_page

    mock_playwright = mocker.AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_playwright.__aenter__ = mocker.AsyncMock(return_value=mock_playwright)
    mock_playwright.__aexit__ = mocker.AsyncMock(return_value=None)

    mocker.patch("playwright.async_api.async_playwright", return_value=mock_playwright)

    result = await parse_url("https://example.com")

    assert len(result) >= 1
    assert any("test content" in block.get("text", "").lower() for block in result)


@pytest.mark.asyncio
async def test_url_parser_handles_network_error(mocker):
    """URL parser handles Playwright errors gracefully."""
    from backend.ingestion.parsers.url_parser import parse_url

    mock_playwright = mocker.AsyncMock()
    mock_playwright.chromium.launch.side_effect = Exception("Network error")
    mock_playwright.__aenter__ = mocker.AsyncMock(return_value=mock_playwright)
    mock_playwright.__aexit__ = mocker.AsyncMock(return_value=None)

    mocker.patch("playwright.async_api.async_playwright", return_value=mock_playwright)

    with pytest.raises(Exception):
        await parse_url("https://example.com")


def test_url_parser_validates_scheme():
    """URL parser only accepts http/https."""
    from backend.ingestion.parsers.url_parser import parse_url
    # The actual validation happens in documents.py before parse_url is called
    # But we can test that non-http URLs are rejected early
    with pytest.raises(Exception):
        # This should fail before Playwright even starts
        import asyncio
        asyncio.run(parse_url("ftp://example.com"))
