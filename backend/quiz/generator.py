"""LLM-powered quiz generator.

Samples random chunks from the selected documents and asks the LLM
to produce MCQ or flashcard questions grounded in that content.
"""
from __future__ import annotations

import json
import random
from typing import List, Optional

from fastapi import HTTPException

from sqlmodel import Session, select

from backend.database import Chunk, Quiz, engine
from backend.llm.openrouter import complete
from backend.quiz.schemas import MCQQuestion, MCQOption, Flashcard, QuizResult

MCQ_SYSTEM = """You are an expert educator creating multiple-choice quiz questions.
Given source text, generate exactly {n} multiple-choice questions.
Each question must be answerable from the provided text only.

Respond with ONLY a JSON array, no markdown, no explanation:
[
  {{
    "question": "...",
    "options": [
      {{"label": "A", "text": "..."}},
      {{"label": "B", "text": "..."}},
      {{"label": "C", "text": "..."}},
      {{"label": "D", "text": "..."}}
    ],
    "answer": "A",
    "explanation": "Brief explanation of why this is correct."
  }}
]"""

FLASHCARD_SYSTEM = """You are an expert educator creating flashcards for spaced repetition.
Given source text, generate exactly {n} flashcards.
Each card: front = concise question or term, back = clear answer or definition.

Respond with ONLY a JSON array, no markdown:
[
  {{
    "front": "...",
    "back": "...",
    "hint": "optional one-word hint or null"
  }}
]"""


ERROR_CORRECTION_PROMPT = """The previous response was invalid JSON. Please respond with ONLY a valid JSON array, no markdown fences, no explanations."""


async def generate_quiz(
    doc_ids: List[str],
    quiz_type: str = "mcq",
    n_questions: int = 5,
) -> QuizResult:
    """
    Generate a quiz from chunks belonging to the given documents.

    Args:
        doc_ids:     Documents to sample from.
        quiz_type:   "mcq" or "flashcard"
        n_questions: Number of questions/cards to generate.

    Returns:
        QuizResult with populated questions or flashcards.

    Raises:
        HTTPException: If LLM returns malformed JSON after retry.
    """
    # Sample chunks from the selected docs
    chunks = _sample_chunks(doc_ids, n_samples=min(n_questions * 3, 15))
    if not chunks:
        raise ValueError("No chunks found for the selected documents")

    context = "\n\n---\n\n".join(c.text for c in chunks)

    # Build prompt
    if quiz_type == "mcq":
        system = MCQ_SYSTEM.format(n=n_questions)
    else:
        system = FLASHCARD_SYSTEM.format(n=n_questions)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Source text:\n\n{context}"},
    ]

    # First attempt
    try:
        raw = await complete(messages, max_tokens=2048, temperature=0.7)
        data = _parse_json_response(raw)
    except json.JSONDecodeError as e:
        # Retry once with error correction
        messages.append({"role": "assistant", "content": f"Previous response was invalid JSON: {e}"})
        messages.append({"role": "user", "content": ERROR_CORRECTION_PROMPT})
        try:
            raw = await complete(messages, max_tokens=2048, temperature=0.7)
            data = _parse_json_response(raw)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=502,
                detail="LLM returned malformed JSON after retry"
            )

    # Validate structure based on quiz_type
    if quiz_type == "mcq":
        if not isinstance(data, list):
            raise HTTPException(status_code=502, detail="Expected JSON array for MCQ")
        for item in data:
            if not all(k in item for k in ("question", "options", "answer")):
                raise HTTPException(status_code=502, detail="MCQ missing required fields")
    else:
        if not isinstance(data, list):
            raise HTTPException(status_code=502, detail="Expected JSON array for flashcards")
        for item in data:
            if not all(k in item for k in ("front", "back")):
                raise HTTPException(status_code=502, detail="Flashcard missing required fields")

    mcq_questions = []
    flashcards = []

    if quiz_type == "mcq":
        for item in data:
            mcq_questions.append(MCQQuestion(
                question=item["question"],
                options=[MCQOption(**o) for o in item["options"]],
                answer=item["answer"],
                explanation=item.get("explanation", ""),
            ))
    else:
        for item in data:
            flashcards.append(Flashcard(
                front=item["front"],
                back=item["back"],
                hint=item.get("hint"),
            ))

    # Persist quiz to DB
    quiz_id = _save_quiz(doc_ids, quiz_type, mcq_questions, flashcards)

    return QuizResult(
        quiz_id=quiz_id,
        quiz_type=quiz_type,
        doc_ids=doc_ids,
        questions=mcq_questions,
        flashcards=flashcards,
    )


def _parse_json_response(raw: str) -> list:
    """
    Extract and parse JSON from LLM response.

    Handles markdown code fences (```json ... ```).

    Args:
        raw: Raw LLM response string.

    Returns:
        Parsed JSON data (list).

    Raises:
        json.JSONDecodeError: If response is not valid JSON.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
    raw = raw.strip()
    return json.loads(raw)


def _sample_chunks(doc_ids: List[str], n_samples: int) -> List[Chunk]:
    with Session(engine) as db:
        query = select(Chunk)
        if doc_ids:
            query = query.where(Chunk.doc_id.in_(doc_ids))
        all_chunks = db.exec(query).all()

    if not all_chunks:
        return []

    # Prefer longer, more informative chunks
    weighted = [c for c in all_chunks if c.token_count > 50]
    pool = weighted if weighted else all_chunks
    return random.sample(pool, min(n_samples, len(pool)))


def _save_quiz(doc_ids, quiz_type, questions, flashcards) -> int:
    import json as _json
    q_data = (
        [q.model_dump() for q in questions]
        if questions
        else [f.model_dump() for f in flashcards]
    )
    quiz = Quiz(
        doc_ids=_json.dumps(doc_ids),
        questions=_json.dumps(q_data),
        quiz_type=quiz_type,
    )
    with Session(engine) as db:
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        return quiz.id
