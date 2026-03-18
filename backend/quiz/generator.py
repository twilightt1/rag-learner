"""LLM-powered quiz generator.

Samples random chunks from the selected documents and asks the LLM
to produce MCQ or flashcard questions grounded in that content.
"""
import json
import random
from typing import List, Optional

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


async def generate_quiz(
    doc_ids: List[int],
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

    raw = await complete(messages, max_tokens=2048, temperature=0.7)

    # Parse JSON response
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)

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


def _sample_chunks(doc_ids: List[int], n_samples: int) -> List[Chunk]:
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
