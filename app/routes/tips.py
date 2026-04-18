import uuid
import json
from datetime import date
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.journal import JournalSession, JournalEntry
from app.services.context_builder import build_context
from app.services.tip_generator import generate_questions
from app.services import claude_runner

router = APIRouter(prefix="/tips", tags=["tips"])


def _run_session(session_id: str, questions: list[str], db: Session):
    for q in questions:
        entry = db.query(JournalEntry).filter(
            JournalEntry.session_id == session_id,
            JournalEntry.question == q,
        ).first()
        if not entry:
            continue
        response, status = claude_runner.ask(q)
        entry.response = response
        entry.status = status
        db.commit()


@router.post("/daily")
def create_daily_session(
    background_tasks: BackgroundTasks,
    lat: float = 60.38,
    lng: float = 24.51,
    node_name: str = "farm",
    db: Session = Depends(get_db),
):
    """
    Build context, generate 10 questions, persist them, then fire
    each to Claude CLI in the background. Returns the session ID
    immediately — poll /tips/session/{id} for results.
    """
    context = build_context(lat=lat, lng=lng, node_name=node_name)
    questions = generate_questions(context)

    session_id = str(uuid.uuid4())
    session = JournalSession(
        id=session_id,
        context_json=json.dumps(context),
        node_id=None,
    )
    db.add(session)

    entries = []
    for q in questions:
        entry = JournalEntry(
            id=str(uuid.uuid4()),
            session_id=session_id,
            question=q,
            status="pending",
        )
        db.add(entry)
        entries.append(q)

    db.commit()

    background_tasks.add_task(_run_session, session_id, entries, db)

    return {"session_id": session_id, "question_count": len(entries), "status": "running"}


@router.get("/session/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Return the context and all tip entries for a session."""
    session = db.query(JournalSession).filter(JournalSession.id == session_id).first()
    if not session:
        return {"error": "session not found"}

    entries = db.query(JournalEntry).filter(JournalEntry.session_id == session_id).all()
    pending = sum(1 for e in entries if e.status == "pending")

    return {
        "session_id": session_id,
        "context": json.loads(session.context_json),
        "status": "running" if pending > 0 else "complete",
        "tips": [
            {
                "question": e.question,
                "response": e.response,
                "status": e.status,
            }
            for e in entries
        ],
    }


@router.get("/today")
def get_today(db: Session = Depends(get_db)):
    """Return the most recent session from today."""
    today = date.today().isoformat()
    session = (
        db.query(JournalSession)
        .filter(JournalSession.created_at >= today)
        .order_by(JournalSession.created_at.desc())
        .first()
    )
    if not session:
        return {"tips": [], "message": "No session today. POST /tips/daily to generate."}

    entries = db.query(JournalEntry).filter(JournalEntry.session_id == session.id).all()
    return {
        "session_id": session.id,
        "tips": [
            {"question": e.question, "response": e.response, "status": e.status}
            for e in entries
        ],
    }
