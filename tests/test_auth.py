"""Authentication tests (TC-01 … TC-04, TC-26, TC-27)."""
from tests.conftest import auth_headers, register_user


def test_tc01_register_success(client):
    """TC-01: A valid registration creates the account and returns a token."""
    token, user = register_user(client, username="newuser", email="new@example.com")
    assert token
    assert user["username"] == "newuser"
    assert "password" not in user and "password_hash" not in user


def test_tc02_duplicate_email_rejected(client):
    """TC-02: Registering the same email twice returns 409."""
    register_user(client, username="first", email="dup@example.com")
    response = client.post(
        "/api/register",
        json={
            "name": "Second",
            "username": "second",
            "email": "dup@example.com",
            "password": "Password123",
        },
    )
    assert response.status_code == 409
    assert "already exists" in response.get_json()["error"]


def test_tc02b_duplicate_username_rejected(client):
    register_user(client, username="taken", email="a@example.com")
    response = client.post(
        "/api/register",
        json={
            "name": "Other",
            "username": "taken",
            "email": "b@example.com",
            "password": "Password123",
        },
    )
    assert response.status_code == 409


def test_tc02c_weak_password_rejected(client):
    response = client.post(
        "/api/register",
        json={
            "name": "Weak",
            "username": "weakuser",
            "email": "weak@example.com",
            "password": "short",
        },
    )
    assert response.status_code == 400
    assert "password" in response.get_json()["details"]


def test_tc03_valid_login(client):
    """TC-03: Correct credentials return a JWT."""
    register_user(client, username="logintest", email="login@example.com")
    response = client.post(
        "/api/login",
        json={"identifier": "login@example.com", "password": "Password123"},
    )
    assert response.status_code == 200
    assert response.get_json()["token"]


def test_tc03b_login_with_username(client):
    register_user(client, username="byusername", email="bu@example.com")
    response = client.post(
        "/api/login",
        json={"identifier": "byusername", "password": "Password123"},
    )
    assert response.status_code == 200


def test_tc04_invalid_login(client):
    """TC-04: Wrong password returns 401 with a generic message."""
    register_user(client, username="badlogin", email="bad@example.com")
    response = client.post(
        "/api/login",
        json={"identifier": "bad@example.com", "password": "WrongPassword1"},
    )
    assert response.status_code == 401
    # Must not reveal whether the email exists
    assert "Invalid credentials" in response.get_json()["error"]


def test_tc26_expired_or_invalid_token(client):
    """TC-26: A malformed token is rejected with 401."""
    response = client.get("/api/profile", headers=auth_headers("not.a.real.token"))
    assert response.status_code == 401


def test_missing_token_returns_401(client):
    assert client.get("/api/profile").status_code == 401


def test_tc27_logout(client, user_a):
    """TC-27: Logout succeeds for an authenticated caller."""
    token, _ = user_a
    response = client.post("/api/logout", headers=auth_headers(token))
    assert response.status_code == 200


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["database"] == "up"