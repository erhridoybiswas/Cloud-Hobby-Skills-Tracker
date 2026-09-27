"""Practice tracking and goal progress tests (TC-09 … TC-12)."""
from tests.conftest import auth_headers


def setup_skill_and_goal(client, headers, target=20, unit="hours", milestones=(5, 10, 20)):
    skill = client.post(
        "/api/skills",
        json={"skill_name": "Photography", "category": "Photography"},
        headers=headers,
    ).get_json()["skill"]

    goal = client.post(
        "/api/goals",
        json={
            "skill_id": skill["skill_id"],
            "title": f"Practice {target} {unit}",
            "target_value": target,
            "unit": unit,
            "milestones": [{"title": f"{m} reached", "target_value": m} for m in milestones],
        },
        headers=headers,
    ).get_json()["goal"]

    return skill, goal


def test_tc09_create_goal(client, user_a):
    """TC-09: A goal with milestones is created atomically."""
    token, _ = user_a
    headers = auth_headers(token)
    _, goal = setup_skill_and_goal(client, headers)

    assert goal["target_value"] == 20
    assert goal["current_value"] == 0
    assert goal["progress_percent"] == 0
    assert len(goal["milestones"]) == 3


def test_tc10_log_practice_session(client, user_a):
    """TC-10: Logging practice returns 201 and updates goal progress."""
    token, _ = user_a
    headers = auth_headers(token)
    skill, _ = setup_skill_and_goal(client, headers)

    response = client.post(
        "/api/practice",
        json={
            "skill_id": skill["skill_id"],
            "duration_minutes": 60,
            "activity": "Portrait practice",
            "notes": "Natural light composition",
        },
        headers=headers,
    )
    assert response.status_code == 201

    body = response.get_json()
    assert body["session"]["duration_minutes"] == 60
    # 60 minutes = 1 hour against a 20-hour goal
    assert body["updated_goals"][0]["current_value"] == 1.0


def test_tc11_progress_calculation(client, user_a):
    """TC-11: Progress percentage is computed correctly (6h / 20h = 30%)."""
    token, _ = user_a
    headers = auth_headers(token)
    skill, _ = setup_skill_and_goal(client, headers)

    for _ in range(6):
        client.post(
            "/api/practice",
            json={"skill_id": skill["skill_id"], "duration_minutes": 60},
            headers=headers,
        )

    goals = client.get("/api/goals", headers=headers).get_json()["goals"]
    goal = goals[0]
    assert goal["current_value"] == 6.0
    assert goal["progress_percent"] == 30.0


def test_tc11b_progress_capped_at_100(client, user_a):
    """TC-11: Overshooting a goal caps displayed progress at 100%."""
    token, _ = user_a
    headers = auth_headers(token)
    skill, _ = setup_skill_and_goal(client, headers, target=2, milestones=())

    # Log 5 hours against a 2-hour goal
    for _ in range(5):
        client.post(
            "/api/practice",
            json={"skill_id": skill["skill_id"], "duration_minutes": 60},
            headers=headers,
        )

    goal = client.get("/api/goals", headers=headers).get_json()["goals"][0]
    assert goal["progress_percent"] == 100.0
    assert goal["current_value"] == 5.0     # raw value stays truthful
    assert goal["status"] == "COMPLETED"


def test_tc12_milestone_achievement(client, user_a):
    """TC-12: Crossing a milestone threshold marks it achieved."""
    token, _ = user_a
    headers = auth_headers(token)
    skill, _ = setup_skill_and_goal(client, headers, target=20, milestones=(1, 5, 10))

    response = client.post(
        "/api/practice",
        json={"skill_id": skill["skill_id"], "duration_minutes": 60},
        headers=headers,
    )
    achieved = response.get_json()["new_milestones"]
    assert len(achieved) == 1
    assert achieved[0]["target_value"] == 1


def test_log_practice_for_foreign_skill_rejected(client, user_a, user_b):
    """Authorization: Bob cannot log practice against Alice's skill."""
    token_a, _ = user_a
    token_b, _ = user_b

    skill = client.post(
        "/api/skills",
        json={"skill_name": "Alice Only", "category": "Art"},
        headers=auth_headers(token_a),
    ).get_json()["skill"]

    response = client.post(
        "/api/practice",
        json={"skill_id": skill["skill_id"], "duration_minutes": 30},
        headers=auth_headers(token_b),
    )
    assert response.status_code == 403


def test_invalid_duration_rejected(client, user_a):
    token, _ = user_a
    headers = auth_headers(token)
    skill, _ = setup_skill_and_goal(client, headers)

    response = client.post(
        "/api/practice",
        json={"skill_id": skill["skill_id"], "duration_minutes": 5000},
        headers=headers,
    )
    assert response.status_code == 400
    assert "duration_minutes" in response.get_json()["details"]