"""
习题模块 API 测试 (PBI_08, PBI_09, PBI_10)
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import User


# ── 测试常量 (纯 ASCII 避免编码问题) ──────────────────────────

MOCK_LLM_EXERCISE_RESPONSE = json.dumps(
    [
        {
            "question": "What is the meaning of 'yi' in the text?",
            "question_type": "choice",
            "options": ["A. Strange", "B. Surprised", "C. Different", "D. Special"],
            "answer": "B",
            "analysis": "The word 'yi' is used as an adjective with conative usage.",
            "difficulty": "easy",
            "knowledge_points": ["classical Chinese", "vocabulary"],
        },
        {
            "question": "Please translate the sentence.",
            "question_type": "short_answer",
            "options": None,
            "answer": "The paths crisscross in the fields, and the sounds of chickens and dogs can be heard.",
            "analysis": "Key: paths, crisscross, sounds, heard.",
            "difficulty": "medium",
            "knowledge_points": ["translation", "classical Chinese"],
        },
        {
            "question": "What emotions does the author express?",
            "question_type": "analysis",
            "options": None,
            "answer": "The author expresses longing for an ideal society and dissatisfaction with reality.",
            "analysis": "Two aspects: longing for peace + dissatisfaction with social turmoil.",
            "difficulty": "hard",
            "knowledge_points": ["theme analysis", "essay writing"],
        },
    ],
    ensure_ascii=False,
)

MOCK_LLM_GRADE_RESPONSE = json.dumps(
    [
        {
            "exercise_id": "PLACEHOLDER_1",
            "is_correct": True,
            "score": 20.0,
            "correct_answer": "B",
            "analysis": "The word 'yi' means surprised.",
            "error_reason": None,
            "related_knowledge": ["classical Chinese"],
        },
        {
            "exercise_id": "PLACEHOLDER_2",
            "is_correct": False,
            "score": 12.0,
            "correct_answer": "The paths crisscross in the fields.",
            "analysis": "Key vocabulary: paths, crisscross.",
            "error_reason": "Missing translation of key phrase",
            "related_knowledge": ["translation", "classical Chinese"],
        },
    ],
    ensure_ascii=False,
)


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
async def test_user(db_session) -> User:
    """Create a test user and return it"""
    user = User(
        id=str(uuid.uuid4()),
        email="test_student@example.com",
        hashed_password="hashed_password_placeholder",
        nickname="Test Student",
        grade="Grade 7",
        subjects=["Chinese", "Math"],
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user) -> dict:
    """Generate auth headers with Bearer token"""
    token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {token}"}


# ── Generate Exercises (POST /exercises/generate) ──────────────


@pytest.mark.asyncio
async def test_generate_exercises_success(
    client: AsyncClient, auth_headers: dict
):
    """Normal exercise generation with SSE streaming"""
    with patch(
        "app.services.exercise_service.llm_client.chat_with_retry",
        new_callable=AsyncMock,
        return_value=MOCK_LLM_EXERCISE_RESPONSE,
    ):
        response = await client.post(
            "/api/v1/exercises/generate",
            json={
                "subject": "Chinese",
                "grade": "Grade 7",
                "knowledge_points": ["classical Chinese", "translation"],
                "difficulty": "medium",
                "question_types": ["choice", "short_answer", "analysis"],
                "count": 3,
                "mode": "practice",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        body = response.text
        events = _parse_sse(body)

        assert len(events) >= 2
        exercise_events = [e for e in events if e["type"] == "exercise"]
        done_events = [e for e in events if e["type"] == "done"]

        assert len(exercise_events) == 3
        assert len(done_events) == 1
        assert "batch_id" in done_events[0]
        assert len(done_events[0]["exercises"]) == 3

        # Practice mode: answers should be null
        first_ex = exercise_events[0]["exercise"]
        assert first_ex["answer"] is None
        assert first_ex["analysis"] is None


@pytest.mark.asyncio
async def test_generate_exercises_review_mode(
    client: AsyncClient, auth_headers: dict
):
    """Review mode returns full answers"""
    with patch(
        "app.services.exercise_service.llm_client.chat_with_retry",
        new_callable=AsyncMock,
        return_value=MOCK_LLM_EXERCISE_RESPONSE,
    ):
        response = await client.post(
            "/api/v1/exercises/generate",
            json={
                "subject": "Chinese",
                "grade": "Grade 7",
                "knowledge_points": ["classical Chinese"],
                "difficulty": "easy",
                "question_types": ["choice"],
                "count": 3,
                "mode": "review",
            },
            headers=auth_headers,
        )
        body = response.text
        events = _parse_sse(body)
        exercise_events = [e for e in events if e["type"] == "exercise"]

        first_ex = exercise_events[0]["exercise"]
        assert first_ex["answer"] is not None
        assert first_ex["analysis"] is not None


@pytest.mark.asyncio
async def test_generate_exercises_unauthorized(client: AsyncClient):
    """Unauthenticated request returns 401"""
    response = await client.post(
        "/api/v1/exercises/generate",
        json={
            "subject": "Chinese",
            "grade": "Grade 7",
            "knowledge_points": ["test"],
            "count": 3,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_generate_exercises_llm_error(
    client: AsyncClient, auth_headers: dict
):
    """LLM returns invalid JSON -> 500 with LLM_SERVICE_ERROR"""
    with patch(
        "app.services.exercise_service.llm_client.chat_with_retry",
        new_callable=AsyncMock,
        return_value="This is not valid JSON",
    ):
        response = await client.post(
            "/api/v1/exercises/generate",
            json={
                "subject": "Math",
                "grade": "Grade 8",
                "knowledge_points": ["Pythagorean theorem"],
                "count": 3,
            },
            headers=auth_headers,
        )
        assert response.status_code == 500
        detail = response.json()["detail"]
        assert detail["code"] == 50002


# ── Grade API (POST /exercises/grade) ───────────────────────────


@pytest.mark.asyncio
async def test_grade_answers_success(
    client: AsyncClient, test_user: User, db_session, auth_headers: dict
):
    """Normal grading flow: create exercises then grade them"""
    from app.models.exercise import Exercise

    exercise_ids = []
    for i in range(2):
        ex = Exercise(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            batch_id=str(uuid.uuid4()),
            subject="Chinese",
            grade="Grade 7",
            question_type="choice" if i == 0 else "short_answer",
            question="Test question " + str(i),
            options=["A", "B", "C", "D"] if i == 0 else None,
            answer="B" if i == 0 else "Correct answer",
            analysis="Analysis text",
            difficulty="easy",
            knowledge_points=["knowledge point"],
        )
        db_session.add(ex)
        exercise_ids.append(ex.id)
    await db_session.commit()

    mock_grade = MOCK_LLM_GRADE_RESPONSE.replace(
        "PLACEHOLDER_1", exercise_ids[0]
    ).replace("PLACEHOLDER_2", exercise_ids[1])

    with patch(
        "app.services.exercise_service.llm_client.chat_with_retry",
        new_callable=AsyncMock,
        return_value=mock_grade,
    ):
        response = await client.post(
            "/api/v1/exercises/grade",
            json={
                "batch_id": str(uuid.uuid4()),
                "answers": [
                    {"exercise_id": exercise_ids[0], "user_answer": "B"},
                    {"exercise_id": exercise_ids[1], "user_answer": "Wrong answer"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["total_count"] == 2
        assert data["correct_count"] == 1
        assert "results" in data
        assert len(data["results"]) == 2


@pytest.mark.asyncio
async def test_grade_answers_empty(
    client: AsyncClient, auth_headers: dict
):
    """Empty answers list returns 400"""
    response = await client.post(
        "/api/v1/exercises/grade",
        json={"answers": []},
        headers=auth_headers,
    )
    assert response.status_code == 400


# ── History API (GET /exercises/history) ───────────────────────


@pytest.mark.asyncio
async def test_get_history_empty(
    client: AsyncClient, auth_headers: dict
):
    """New user has no history"""
    response = await client.get(
        "/api/v1/exercises/history", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["items"] == []
    assert data["data"]["total"] == 0


@pytest.mark.asyncio
async def test_get_history_with_data(
    client: AsyncClient, test_user: User, db_session, auth_headers: dict
):
    """History returns batch list when data exists"""
    from app.models.exercise import Exercise

    batch_id = str(uuid.uuid4())
    for i in range(5):
        ex = Exercise(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            batch_id=batch_id,
            subject="Chinese",
            grade="Grade 7",
            question_type="choice" if i % 2 == 0 else "fill",
            question=f"Question {i}",
            options=["A", "B", "C", "D"] if i % 2 == 0 else None,
            answer="A",
            analysis="Analysis",
            difficulty="easy",
            knowledge_points=["Knowledge Point 1"],
        )
        db_session.add(ex)
    await db_session.commit()

    response = await client.get(
        "/api/v1/exercises/history", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["batch_id"] == batch_id
    assert data["items"][0]["count"] == 5


@pytest.mark.asyncio
async def test_get_history_filter_subject(
    client: AsyncClient, test_user: User, db_session, auth_headers: dict
):
    """Filter history by subject"""
    from app.models.exercise import Exercise

    ex1 = Exercise(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        batch_id=str(uuid.uuid4()),
        subject="Chinese",
        grade="Grade 7",
        question_type="choice",
        question="Chinese question",
        answer="A",
        difficulty="easy",
        knowledge_points=[],
    )
    ex2 = Exercise(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        batch_id=str(uuid.uuid4()),
        subject="Math",
        grade="Grade 7",
        question_type="calculation",
        question="Math question",
        answer="42",
        difficulty="medium",
        knowledge_points=[],
    )
    db_session.add_all([ex1, ex2])
    await db_session.commit()

    response = await client.get(
        "/api/v1/exercises/history",
        params={"subject": "Math"},
        headers=auth_headers,
    )
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["subject"] == "Math"


# ── Batch Detail API (GET /exercises/batches/{batch_id}) ────────


@pytest.mark.asyncio
async def test_get_batch_detail(
    client: AsyncClient, test_user: User, db_session, auth_headers: dict
):
    """Batch detail returns exercises and attempts"""
    from app.models.exercise import Exercise, ExerciseAttempt

    batch_id = str(uuid.uuid4())
    ex = Exercise(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        batch_id=batch_id,
        subject="Chinese",
        grade="Grade 7",
        question_type="short_answer",
        question="Test question",
        answer="Standard answer",
        analysis="Detailed analysis",
        difficulty="medium",
        knowledge_points=["Knowledge A"],
    )
    db_session.add(ex)
    await db_session.flush()

    attempt = ExerciseAttempt(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        exercise_id=ex.id,
        user_answer="Student answer",
        is_correct=False,
        score=5.0,
        graded_by="auto",
    )
    db_session.add(attempt)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/exercises/batches/{batch_id}", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["batch_id"] == batch_id
    assert data["subject"] == "Chinese"
    assert len(data["exercises"]) == 1
    assert data["exercises"][0]["answer"] == "Standard answer"
    assert data["exercises"][0]["user_answer"] == "Student answer"
    assert data["exercises"][0]["is_correct"] is False


@pytest.mark.asyncio
async def test_get_batch_detail_not_found(
    client: AsyncClient, auth_headers: dict
):
    """Non-existent batch returns 404"""
    response = await client.get(
        f"/api/v1/exercises/batches/{uuid.uuid4()}", headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_batch_detail_wrong_user(
    client: AsyncClient, test_user: User, db_session, auth_headers: dict
):
    """Cannot access another user's batch"""
    from app.models.exercise import Exercise

    other_batch = str(uuid.uuid4())
    ex = Exercise(
        id=str(uuid.uuid4()),
        user_id="other_user_id",
        batch_id=other_batch,
        subject="Chinese",
        grade="Grade 7",
        question_type="choice",
        question="Should not be visible",
        answer="B",
        difficulty="easy",
        knowledge_points=[],
    )
    db_session.add(ex)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/exercises/batches/{other_batch}", headers=auth_headers
    )
    assert response.status_code == 404


# ── Delete Batch API (DELETE /exercises/batches/{batch_id}) ─────


@pytest.mark.asyncio
async def test_delete_batch(
    client: AsyncClient, test_user: User, db_session, auth_headers: dict
):
    """Normal batch deletion"""
    from app.models.exercise import Exercise

    batch_id = str(uuid.uuid4())
    for i in range(3):
        ex = Exercise(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            batch_id=batch_id,
            subject="Chinese",
            grade="Grade 7",
            question_type="choice",
            question=f"Question {i}",
            answer="A",
            difficulty="easy",
            knowledge_points=[],
        )
        db_session.add(ex)
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/exercises/batches/{batch_id}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] == 3

    # Verify deleted
    response2 = await client.get(
        f"/api/v1/exercises/batches/{batch_id}", headers=auth_headers
    )
    assert response2.status_code == 404


@pytest.mark.asyncio
async def test_delete_batch_not_found(
    client: AsyncClient, auth_headers: dict
):
    """Deleting non-existent batch returns 404"""
    response = await client.delete(
        f"/api/v1/exercises/batches/{uuid.uuid4()}", headers=auth_headers
    )
    assert response.status_code == 404


# ── Validation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_exercises_validation_error(
    client: AsyncClient, auth_headers: dict
):
    """Count exceeds max -> 422"""
    response = await client.post(
        "/api/v1/exercises/generate",
        json={
            "subject": "Chinese",
            "grade": "Grade 7",
            "knowledge_points": ["test"],
            "count": 100,
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


# ── Helpers ─────────────────────────────────────────────────────


def _parse_sse(body: str) -> list[dict]:
    """Parse SSE response body into list of event dicts"""
    events = []
    for line in body.strip().split("\n"):
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events
