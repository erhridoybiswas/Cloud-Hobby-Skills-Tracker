"""Analytics tests (TC-22) plus pure-function streak tests."""
from datetime import date, timedelta

from analytics.progress_service import (
    calculate_progress,
    current_streak,
    longest_streak,
    minutes_since,
    minutes_to_hours,
)
from tests.conftest import auth_headers


# ---------------------------------------------------------------------
# Pure function tests — fast, no HTTP, no database
# ---------------------------------------------------------------------
def test_calculate_progress_basic():
    assert calculate_progress(0, 30) == 0.0
    assert calculate_progress(15, 30) == 50.0
    assert calculate_progress(30, 30) == 100.0


def test_calculate_progress_caps_at_100():
    assert calculate_progress(45, 30) == 100.0


def test_calculate_progress_handles_zero_target():
    """Division by zero must never crash the dashboard."""
    assert calculate_progress(10, 0) == 0.0
    assert calculate_progress(10, -5) == 0.0


def test_current_streak_empty():
    assert current_streak([]) == 0


def test_current_streak_counts_consecutive_days():
    today = date(2024, 6, 10)
    dates = [
        today.isoformat(),
        (today - timedelta(days=1)).isoformat(),
        (today - timedelta(days=2)).isoformat(),
    ]
    assert current_streak(dates, today=today) == 3


def test_current_streak_allows_yesterday_start():
    """A streak stays alive if the user has not practiced yet today."""
    today = date(2024, 6, 10)
    dates = [
        (today - timedelta(days=1)).isoformat(),
        (today - timedelta(days=2)).isoformat(),
    ]
    assert current_streak(dates, today=today) == 2


def test_current_streak_broken_by_gap():
    today = date(2024, 6, 10)
    dates = [today.isoformat(), (today - timedelta(days=5)).isoformat()]
    assert current_streak(dates, today=today) == 1


def test_current_streak_deduplicates_same_day():
    today = date(2024, 6, 10)
    dates = [today.isoformat(), today.isoformat(), today.isoformat()]
    assert current_streak(dates, today=today) == 1


def test_longest_streak():
    dates = [
        "2024-06-01", "2024-06-02", "2024-06-03",   # 3-day run
        "2024-06-07", "2024-06-08", "2024-06-09", "2024-06-10",  # 4-day run
    ]
    assert longest_streak(dates) == 4


def test_minutes_since_filters_by_date():
    today = date(2024, 6, 10)
    sessions = [
        {"practiced_at": "2024-06-10", "duration_minutes": 60},
        {"practiced_at": "2024-06-08", "duration_minutes": 30},
        {"practiced_at": "2024-05-01", "duration_minutes": 120},
    ]
    assert minutes_since(sessions, 7, reference=today) == 90
    assert minutes_since(sessions, 1, reference=today) == 60


def test_minutes_to_hours():
    assert minutes_to_hours(90) == 1.5
    assert minutes_to_hours(0) == 0.0


# ---------------------------------------------------------------------
# End-to-end analytics endpoint
# ---------------------------------------------------------------------
def test_tc22_dashboard_analytics(client, user_a):
    """TC-22: The dashboard aggregates practice correctly."""
    token, _ = user_a
    headers = auth_headers(token)

    skill = client.post(
        "/api/skills",
        json={"skill_name": "Guitar", "category": "Music"},
        headers=headers,
    ).get_json()["skill"]

    client.post(
        "/api/goals",
        json={
            "skill_id": skill["skill_id"],
            "title": "Practice 10 hours",
            "target_value": 10,
            "unit": "hours",
        },
        headers=headers,
    )

    # Log 3 sessions of 60 minutes = 3 hours
    for _ in range(3):
        client.post(
            "/api/practice",
            json={"skill_id": skill["skill_id"], "duration_minutes": 60},
            headers=headers,
        )

    data = client.get("/api/analytics/dashboard", headers=headers).get_json()
    summary = data["summary"]

    assert summary["total_practice_minutes"] == 180
    assert summary["total_practice_hours"] == 3.0
    assert summary["weekly_practice_hours"] == 3.0
    assert summary["current_streak"] == 1
    assert summary["active_skills"] == 1
    assert summary["total_skills"] == 1

    charts = data["charts"]
    assert len(charts["practice_by_skill"]) == 1
    assert charts["practice_by_skill"][0]["label"] == "Guitar"
    assert charts["practice_by_skill"][0]["value"] == 3.0


def test_dashboard_requires_auth(client):
    assert client.get("/api/analytics/dashboard").status_code == 401


def test_dashboard_is_user_scoped(client, user_a, user_b):
    """Each user sees only their own analytics."""
    token_a, _ = user_a
    token_b, _ = user_b

    skill_a = client.post(
        "/api/skills",
        json={"skill_name": "Alice Art", "category": "Art"},
        headers=auth_headers(token_a),
    ).get_json()["skill"]

    client.post(
        "/api/practice",
        json={"skill_id": skill_a["skill_id"], "duration_minutes": 120},
        headers=auth_headers(token_a),
    )

    bob_dashboard = client.get("/api/analytics/dashboard", headers=auth_headers(token_b)).get_json()
    assert bob_dashboard["summary"]["total_practice_minutes"] == 0