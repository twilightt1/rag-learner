from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class MCQOption(BaseModel):
    label: str   # A, B, C, D
    text: str


class MCQQuestion(BaseModel):
    question: str
    options: List[MCQOption]
    answer: str       # correct label: "A" | "B" | "C" | "D"
    explanation: str


class Flashcard(BaseModel):
    front: str
    back: str
    hint: Optional[str] = None


class QuizResult(BaseModel):
    quiz_id: str
    quiz_type: str    # mcq | flashcard
    doc_ids: List[str]
    questions: List[MCQQuestion] = []
    flashcards: List[Flashcard] = []
