"""
Shared pytest fixtures.

Each test gets a fresh SQLite database and a fresh upload directory in a
temporary folder, so tests never interfere with each other or with your
development data.
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app import create_app  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    """A Flask app bound to a throwaway database and upload folder."""
    application = create_app(
        overrides={
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "DATABASE_PATH": str(tmp_path / "test.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "STORAGE_BACKEND": "local",
            "MAX_CONTENT_LENGTH": 5 * 1024 * 1024,
        }
    )
    yield application


@pytest.fixture()
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


def register_user(client, username="testuser", email=None, password="Password123"):
    """Helper: register a user and return (token, user_dict)."""
    email = email or f"{username}@example.com"
    response = client.post(
        "/api/register",
        json={
            "name": f"Test {username.title()}",
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, response.get_json()
    payload = response.get_json()
    return payload["token"], payload["user"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_a(client):
    """Token + user for the first test account."""
    return register_user(client, username="alice", email="alice@example.com")


@pytest.fixture()
def user_b(client):
    """Token + user for the second test account."""
    return register_user(client, username="bob", email="bob@example.com")


@pytest.fixture()
def auth_client(client, user_a):
    """A client with Alice's token pre-attached via a helper attribute."""
    client.token = user_a[0]
    client.user = user_a[1]
    client.headers_auth = auth_headers(user_a[0])
    return client