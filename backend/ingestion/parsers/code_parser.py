"""Code files → semantic chunks using tree-sitter.

Falls back to line-based chunking if tree-sitter parsing fails.
Supported: Python, JavaScript/TypeScript
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Tuple


def parse_code(file_path: str) -> List[Dict]:
    """
    Parse a source code file into semantic blocks (functions, classes).

    Returns:
        List of dicts with keys: section (name), text, start_line
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    source = path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".py":
        blocks = _parse_python(source)
    elif suffix in (".js", ".jsx", ".ts", ".tsx"):
        blocks = _parse_javascript(source)
    else:
        blocks = _fallback_split(source)

    # Always prepend a "file header" block with the top-level context
    header = _extract_header(source, suffix)
    if header:
        blocks.insert(0, {
            "section": f"file:{path.name}",
            "text": f"# File: {path.name}\n\n{header}",
            "start_line": 0,
        })

    return blocks


def _parse_python(source: str) -> List[Dict]:
    """Extract top-level functions and classes with their docstrings/bodies."""
    try:
        import tree_sitter_python as tspython
        from tree_sitter import Language, Parser

        PY_LANG = Language(tspython.language())
        parser = Parser(PY_LANG)
        tree = parser.parse(source.encode())
        return _extract_tree_sitter_blocks(source, tree, ["function_definition", "class_definition"])
    except Exception:
        return _fallback_split(source)


def _parse_javascript(source: str) -> List[Dict]:
    """Extract functions and classes from JS/TS files."""
    try:
        import tree_sitter_javascript as tsjavascript
        from tree_sitter import Language, Parser

        JS_LANG = Language(tsjavascript.language())
        parser = Parser(JS_LANG)
        tree = parser.parse(source.encode())
        return _extract_tree_sitter_blocks(
            source, tree,
            ["function_declaration", "class_declaration",
             "arrow_function", "method_definition"]
        )
    except Exception:
        return _fallback_split(source)


def _extract_tree_sitter_blocks(source: str, tree, node_types: List[str]) -> List[Dict]:
    """Walk the AST and extract blocks for the given node types."""
    lines = source.splitlines()
    blocks = []

    def walk(node):
        if node.type in node_types:
            start = node.start_point[0]
            end = node.end_point[0] + 1
            block_lines = lines[start:end]
            block_text = "\n".join(block_lines).strip()

            # Get the name if available
            name_node = next(
                (c for c in node.children if c.type in ("identifier", "name")),
                None
            )
            name = source[name_node.start_byte:name_node.end_byte] if name_node else f"block_{start}"

            if block_text and len(block_text) > 20:
                blocks.append({
                    "section": name,
                    "text": block_text,
                    "start_line": start + 1,
                })
        else:
            for child in node.children:
                walk(child)

    walk(tree.root_node)

    # If nothing found, fall back
    return blocks if blocks else _fallback_split(source)


def _fallback_split(source: str) -> List[Dict]:
    """Line-based split for unsupported languages: group into ~40-line blocks."""
    lines = source.splitlines()
    blocks = []
    chunk_size = 40

    for i in range(0, len(lines), chunk_size):
        block = "\n".join(lines[i:i + chunk_size]).strip()
        if block:
            blocks.append({
                "section": f"lines_{i+1}_{min(i+chunk_size, len(lines))}",
                "text": block,
                "start_line": i + 1,
            })

    return blocks


def _extract_header(source: str, suffix: str) -> str:
    """Extract imports and top-level comments as header context."""
    lines = source.splitlines()
    header_lines = []

    for line in lines[:30]:
        stripped = line.strip()
        if (
            stripped.startswith("#")
            or stripped.startswith("//")
            or stripped.startswith('"""')
            or stripped.startswith("'''")
            or stripped.startswith("import ")
            or stripped.startswith("from ")
            or stripped.startswith("require(")
            or stripped.startswith("const ")
            or not stripped  # blank line
        ):
            header_lines.append(line)
        else:
            break

    return "\n".join(header_lines).strip()
