from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import QuizResult
from ..schemas import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizQuestionOut,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from ..services import quiz_service
from ..services.ai_service import AIService, get_ai_service

router = APIRouter(prefix="/api/quiz", tags=["MCQ Quiz"])


@router.post("/generate", response_model=QuizGenerateResponse)
def generate_quiz(req: QuizGenerateRequest, ai: AIService = Depends(get_ai_service)):
    """Generate MCQs. Correct answers are NOT included; they are revealed on submit."""
    questions = quiz_service.generate_questions(ai, req.subject, req.topic, req.num_questions, req.difficulty)
    quiz_id = quiz_service.store_quiz(req.subject, req.topic, req.difficulty, questions)
    return QuizGenerateResponse(
        quiz_id=quiz_id,
        subject=req.subject,
        topic=req.topic,
        difficulty=req.difficulty,
        questions=[QuizQuestionOut(number=i + 1, question=q.question, options=q.options) for i, q in enumerate(questions)],
    )


@router.post("/submit", response_model=QuizSubmitResponse)
def submit_quiz(req: QuizSubmitRequest, db: Session = Depends(get_db)):
    """Score the answers on the server and save the result."""
    quiz = quiz_service.get_quiz(req.quiz_id)
    if quiz is None:
        raise HTTPException(404, "This quiz has expired or was already submitted. Please generate a new quiz.")
    if len(req.answers) != len(quiz["questions"]):
        raise HTTPException(422, f"Expected {len(quiz['questions'])} answers but received {len(req.answers)}.")

    result = quiz_service.score_quiz(quiz["questions"], req.answers)
    topic = f"{quiz['subject']} - {quiz['topic']}"
    record = QuizResult(
        topic=topic[:250],
        difficulty=quiz["difficulty"],
        total_questions=result["total_questions"],
        correct_answers=result["correct_answers"],
        score_percentage=result["score_percentage"],
    )
    db.add(record)
    db.commit()
    quiz_service.remove_quiz(req.quiz_id)
    return QuizSubmitResponse(result_id=record.id, topic=topic, difficulty=quiz["difficulty"], **result)
