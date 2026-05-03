from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
def list_sessions(request: Request) -> list[dict]:
    store = request.app.state.store
    return store.list_sessions()


@router.get("/{session_id}")
def get_session(session_id: str, request: Request) -> dict:
    store = request.app.state.store
    try:
        saved = store.load(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    session = saved.interview_session
    report = saved.score_report

    return {
        "session": {
            "config": session.config.model_dump(),
            "completion_status": saved.completion_status,
            "turns": [
                {
                    "question": {
                        "id": t.question.id,
                        "text": t.question.text,
                        "tags": t.question.tags,
                        "difficulty": t.question.difficulty,
                        "follow_up": t.question.follow_up,
                    },
                    "answer": t.answer,
                    "follow_ups": [{"question": q, "answer": a} for q, a in t.follow_ups],
                    "clarifications": [{"candidate": cq, "agent": ca} for cq, ca in t.clarifications],
                    "skipped": t.skipped,
                }
                for t in session.turns
            ],
        },
        "report": {
            "scores": [
                {
                    "question_id": s.question_id,
                    "question_text": s.question_text,
                    "answer": s.answer,
                    "star_score": s.star_score,
                    "relevance_score": s.relevance_score,
                    "clarity_score": s.clarity_score,
                    "overall": s.overall,
                    "feedback": s.feedback,
                }
                for s in report.scores
            ],
            "average_overall": report.average_overall,
            "average_star": report.average_star,
            "average_relevance": report.average_relevance,
            "average_clarity": report.average_clarity,
            "summary": report.summary,
        },
    }
