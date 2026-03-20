"""Assembles the LLM prompt from retrieved context + chat history."""
from __future__ import annotations

from typing import List, Dict, Any

SYSTEM_PROMPT = """You are a study assistant helping a student understand their course materials.

Answer questions based ONLY on the provided context excerpts from the student's documents.
If the answer isn't clearly in the context, say so honestly — do not hallucinate.

When answering:
- Be clear and educational, as if explaining to the student
- Reference specific parts of the context when relevant
- If asked to explain a concept, structure your answer with clarity
- Keep answers concise unless the student asks for depth
- **For any mathematical expressions, use LaTeX notation:**
  - Inline formulas: wrap with `\\( ... \\)`
  - Display (block) formulas: wrap with `\\[ ... \\]`
  - Example: `\\(x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\\)` or `\\[ \\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2} \\]`
- This ensures formulas render beautifully and are easy to read

At the end of your answer, you may note which source chunk(s) you drew from."""


def build_messages(
    query: str,
    context_chunks: List[Dict[str, Any]],
    history: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """
    Build the messages list for the OpenRouter chat completion API.

    Args:
        query:          Current user question.
        context_chunks: Retrieved + reranked chunks from retriever.
        history:        Previous messages [{role, content}, ...]

    Returns:
        Messages list ready for the OpenRouter /chat/completions endpoint.
    """
    # Format context block
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        meta = chunk.get("metadata", {})
        source_label = _format_source_label(meta, i)
        context_parts.append(f"[{source_label}]\n{chunk['text']}")

    context_block = "\n\n---\n\n".join(context_parts)

    user_content = f"""Context from your documents:

{context_block}

---

Question: {query}"""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_content})

    return messages


def _format_source_label(meta: Dict, index: int) -> str:
    parts = [f"Source {index}"]
    if meta.get("section"):
        parts.append(f"section: {meta['section']}")
    if meta.get("page_num"):
        parts.append(f"page {meta['page_num']}")
    return ", ".join(parts)
