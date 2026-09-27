"""Skill management tests (TC-05 … TC-08, TC-23)."""
from tests.conftest import auth_headers, register_user


def create_skill(client, headers, name="Photography", **overrides):
    payload = {
        "skill_name": name,
        "category": "Photography",
        "current_level": "BEGINNER",
        "target_level": "INTERMEDIATE",
        "description": "Learning composition",
    }
    payload.update(overrides)
    return client.post("/api/skills", json=payload, headers=headers)


def test_tc05_profile_update(client, user_a):
    """TC-05: A user can update their own profile."""
    token, _ = user_a
    response = client.put(
        "/api/profile",
        json={"name": "Alice Updated", "bio": "Photographer", "interests": "Photography, Chess"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    user = response.get_json()["user"]
    assert user["name"] == "Alice Updated"
    assert user["bio"] == "Photographer"


def test_tc05b_public_profile_hides_email(client, user_a):
    register_user(client, username="alice", email="alice@example.com")
    response = client.get("/api/users/alice")
    assert response.status_code == 200
    body = response.get_json()
    assert "email" not in body["user"]


def test_tc06_add_skill(client, user_a):
    """TC-06: Creating a skill returns 201 with computed fields."""
    token, _ = user_a
    response = create_skill(client, auth_headers(token))
    assert response.status_code == 201
    skill = response.get_json()["skill"]
    assert skill["skill_name"] == "Photography"
    assert skill["progress_percent"] == 0
    assert skill["total_practice_hours"] == 0


def test_tc06b_duplicate_skill_name_rejected(client, user_a):
    token, _ = user_a
    headers = auth_headers(token)
    create_skill(client, headers, name="Guitar", category="Music")
    response = create_skill(client, headers, name="guitar", category="Music")
    assert response.status_code == 409


def test_tc07_update_skill(client, user_a):
    """TC-07: A skill can be partially updated."""
    token, _ = user_a
    headers = auth_headers(token)
    skill_id = create_skill(client, headers).get_json()["skill"]["skill_id"]

    response = client.put(
        f"/api/skills/{skill_id}",
        json={"current_level": "INTERMEDIATE", "status": "PAUSED"},
        headers=headers,
    )
    assert response.status_code == 200
    skill = response.get_json()["skill"]
    assert skill["current_level"] == "INTERMEDIATE"
    assert skill["status"] == "PAUSED"


def test_tc08_delete_skill(client, user_a):
    """TC-08: Deleting a skill removes it."""
    token, _ = user_a
    headers = auth_headers(token)
    skill_id = create_skill(client, headers).get_json()["skill"]["skill_id"]

    assert client.delete(f"/api/skills/{skill_id}", headers=headers).status_code == 200
    assert client.get(f"/api/skills/{skill_id}", headers=headers).status_code == 404


def test_tc23_user_data_isolation_read(client, user_a, user_b):
    """TC-23: Bob cannot read Alice's skill even with the correct ID."""
    token_a, _ = user_a
    token_b, _ = user_b

    skill_id = create_skill(client, auth_headers(token_a)).get_json()["skill"]["skill_id"]

    response = client.get(f"/api/skills/{skill_id}", headers=auth_headers(token_b))
    assert response.status_code == 403


def test_tc23b_user_data_isolation_delete(client, user_a, user_b):
    """TC-23: Bob cannot delete Alice's skill."""
    token_a, _ = user_a
    token_b, _ = user_b

    skill_id = create_skill(client, auth_headers(token_a)).get_json()["skill"]["skill_id"]

    response = client.delete(f"/api/skills/{skill_id}", headers=auth_headers(token_b))
    assert response.status_code == 403

    # And the skill is still there for Alice
    assert client.get(f"/api/skills/{skill_id}", headers=auth_headers(token_a)).status_code == 200


def test_tc23c_skill_list_is_scoped(client, user_a, user_b):
    token_a, _ = user_a
    token_b, _ = user_b

    create_skill(client, auth_headers(token_a), name="Alice Guitar", category="Music")
    create_skill(client, auth_headers(token_b), name="Bob Piano", category="Music")

    alice_skills = client.get("/api/skills", headers=auth_headers(token_a)).get_json()["skills"]
    assert len(alice_skills) == 1
    assert alice_skills[0]["skill_name"] == "Alice Guitar"