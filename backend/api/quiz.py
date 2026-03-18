"""Quiz API endpoints.

POST /api/quiz/generate   — generate MCQ or flashcard quiz
GET  /api/quiz            — list all past quizzes
GET  /api/quiz/{id}       — retrieve a quiz
DELETE /api/quiz/{id}     — delete a quiz
"""
import json
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from backend.database import Quiz, get_session
from backend.quiz.generator import generate_quiz
from backend.quiz.schemas import QuizResult

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


class GenerateQuizRequest(BaseModel):
    doc_ids: List[int]
    quiz_type: str = "mcq"       # mcq | flashcard
    n_questions: int = 5


class QuizSummary(BaseModel):
    id: int
    quiz_type: str
    doc_ids: List[int]
    question_count: int
    created_at: datetime


@router.post("/generate", response_model=QuizResult)
async def generate(request: GenerateQuizRequest):
    if request.quiz_type not in ("mcq", "flashcard"):
        raise HTTPException(status_code=400, detail="quiz_type must be 'mcq' or 'flashcard'")
    if not 1 <= request.n_questions <= 20:
        raise HTTPException(status_code=400, detail="n_questions must be between 1 and 20")

    result = await generate_quiz(
        doc_ids=request.doc_ids,
        quiz_type=request.quiz_type,
        n_questions=request.n_questions,
    )
    return result


@router.get("", response_model=List[QuizSummary])
def list_quizzes(db: Session = Depends(get_session)):
    quizzes = db.exec(select(Quiz).order_by(Quiz.created_at.desc())).all()
    return [
        QuizSummary(
            id=q.id,
            quiz_type=q.quiz_type,
            doc_ids=json.loads(q.doc_ids),
            question_count=len(json.loads(q.questions)),
            created_at=q.created_at,
        )
        for q in quizzes
    ]


@router.get("/{quiz_id}", response_model=QuizResult)
def get_quiz(quiz_id: int, db: Session = Depends(get_session)):
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    doc_ids = json.loads(quiz.doc_ids)
    questions_raw = json.loads(quiz.questions)

    from backend.quiz.schemas import MCQQuestion, MCQOption, Flashcard
    if quiz.quiz_type == "mcq":
        questions = [MCQQuestion(**q) for q in questions_raw]
        flashcards = []
    else:
        questions = []
        flashcards = [Flashcard(**f) for f in questions_raw]

    return QuizResult(
        quiz_id=quiz.id,
        quiz_type=quiz.quiz_type,
        doc_ids=doc_ids,
        questions=questions,
        flashcards=flashcards,
    )


@router.delete("/{quiz_id}", status_code=204)
def delete_quiz(quiz_id: int, db: Session = Depends(get_session)):
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    db.delete(quiz)
    db.commit()
