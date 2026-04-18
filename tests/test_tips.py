import json
import uuid
from unittest.mock import patch
from app.models.journal import JournalSession, JournalEntry
from app.services.tip_generator import generate_questions
from app.services.context_builder import build_context


MOCK_CONTEXT = {
    "date": "2026-04-18",
    "time": "09:00",
    "day_of_year": 108,
    "season": "spring",
    "location": {"lat": 60.38, "lng": 24.51},
    "node_name": "test_farm",
    "weather": {
        "current_temp_c": 8.5,
        "wind_kmh": 12.0,
        "precipitation_mm": 0.0,
        "forecast_3day": [
            {"date": "2026-04-18", "max_c": 10.0, "min_c": 3.0, "precip_mm": 0.0},
            {"date": "2026-04-19", "max_c": 12.0, "min_c": 5.0, "precip_mm": 2.0},
            {"date": "2026-04-20", "max_c": 9.0, "min_c": 4.0, "precip_mm": 5.0},
        ],
    },
}


def test_generate_questions_count():
    questions = generate_questions(MOCK_CONTEXT)
    assert len(questions) == 10


def test_generate_questions_contain_context():
    questions = generate_questions(MOCK_CONTEXT)
    full_text = " ".join(questions)
    assert "2026-04-18" in full_text
    assert "spring" in full_text
    assert "8.5" in full_text


def test_build_context_shape():
    with patch("app.services.context_builder._fetch_weather", return_value=MOCK_CONTEXT["weather"]):
        ctx = build_context(lat=60.38, lng=24.51, node_name="test_farm")
    assert "date" in ctx
    assert "season" in ctx
    assert "weather" in ctx
    assert ctx["location"]["lat"] == 60.38


def test_journal_session_created(db):
    session = JournalSession(
        id=str(uuid.uuid4()),
        context_json=json.dumps(MOCK_CONTEXT),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    assert session.id is not None


def test_journal_entry_append_only(db):
    session = JournalSession(
        id=str(uuid.uuid4()),
        context_json=json.dumps(MOCK_CONTEXT),
    )
    db.add(session)
    db.commit()

    entry = JournalEntry(
        id=str(uuid.uuid4()),
        session_id=session.id,
        question="What should I plant today?",
        status="pending",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    assert entry.status == "pending"
    assert entry.response is None

    entry.response = "Plant early potatoes."
    entry.status = "completed"
    db.commit()
    db.refresh(entry)
    assert entry.status == "completed"


def test_daily_tips_endpoint(client):
    with patch("app.services.claude_runner.ask", return_value=("Plant early potatoes.", "completed")):
        resp = client.post("/tips/daily?lat=60.38&lng=24.51&node_name=test")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["question_count"] == 10


def test_get_session_endpoint(client):
    with patch("app.services.claude_runner.ask", return_value=("Some tip.", "completed")):
        create = client.post("/tips/daily?lat=60.38&lng=24.51")
    session_id = create.json()["session_id"]

    resp = client.get(f"/tips/session/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert len(data["tips"]) == 10


def test_get_session_not_found(client):
    resp = client.get("/tips/session/nonexistent-id")
    assert resp.status_code == 200
    assert "error" in resp.json()
