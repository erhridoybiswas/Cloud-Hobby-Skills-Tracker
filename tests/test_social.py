"""Community & social interaction tests (TC-13 … TC-21)."""
import io

from tests.conftest import auth_headers, register_user


def make_post(client, headers, content="Completed 30 hours of guitar practice!"):
    return client.post("/api/posts", json={"content": content}, headers=headers)


def test_tc15_create_post(client, user_a):
    """TC-15: A user can create a community post."""
    token, _ = user_a
    response = make_post(client, auth_headers(token))
    assert response.status_code == 201
    post = response.get_json()["post"]
    assert post["like_count"] == 0
    assert post["comment_count"] == 0
    assert post["is_mine"] is True


def test_tc15b_empty_post_rejected(client, user_a):
    token, _ = user_a
    response = make_post(client, auth_headers(token), content="   ")
    assert response.status_code == 400


def test_tc16_retrieve_feed(client, user_a, user_b):
    """TC-16: The feed returns posts from all users."""
    token_a, _ = user_a
    token_b, _ = user_b

    make_post(client, auth_headers(token_a), "Alice achievement")
    make_post(client, auth_headers(token_b), "Bob achievement")

    feed = client.get("/api/feed", headers=auth_headers(token_a)).get_json()
    assert feed["total"] == 2
    assert len(feed["posts"]) == 2


def test_tc17_like_post(client, user_a, user_b):
    """TC-17: User B can like User A's post."""
    token_a, _ = user_a
    token_b, _ = user_b

    post_id = make_post(client, auth_headers(token_a)).get_json()["post"]["post_id"]

    response = client.post(f"/api/posts/{post_id}/like", headers=auth_headers(token_b))
    assert response.status_code == 200
    assert response.get_json()["like_count"] == 1


def test_tc18_duplicate_like_prevented(client, user_a, user_b):
    """TC-18: Liking twice does not create a duplicate."""
    token_a, _ = user_a
    token_b, _ = user_b
    headers_b = auth_headers(token_b)

    post_id = make_post(client, auth_headers(token_a)).get_json()["post"]["post_id"]

    client.post(f"/api/posts/{post_id}/like", headers=headers_b)
    second = client.post(f"/api/posts/{post_id}/like", headers=headers_b)

    assert second.status_code == 200
    assert second.get_json()["like_count"] == 1     # still 1, not 2


def test_tc19_unlike_post(client, user_a, user_b):
    """TC-19: Unliking removes the like."""
    token_a, _ = user_a
    token_b, _ = user_b
    headers_b = auth_headers(token_b)

    post_id = make_post(client, auth_headers(token_a)).get_json()["post"]["post_id"]
    client.post(f"/api/posts/{post_id}/like", headers=headers_b)

    response = client.delete(f"/api/posts/{post_id}/like", headers=headers_b)
    assert response.status_code == 200
    assert response.get_json()["like_count"] == 0


def test_tc20_add_and_get_comment(client, user_a, user_b):
    """TC-20: Comments are created and retrievable."""
    token_a, _ = user_a
    token_b, _ = user_b

    post_id = make_post(client, auth_headers(token_a)).get_json()["post"]["post_id"]

    response = client.post(
        f"/api/posts/{post_id}/comments",
        json={"content": "Amazing work! 🎉"},
        headers=auth_headers(token_b),
    )
    assert response.status_code == 201

    comments = client.get(f"/api/posts/{post_id}/comments").get_json()["comments"]
    assert len(comments) == 1
    assert comments[0]["content"] == "Amazing work! 🎉"


def test_tc21_unauthorized_post_deletion(client, user_a, user_b):
    """TC-21: Bob cannot delete Alice's post."""
    token_a, _ = user_a
    token_b, _ = user_b

    post_id = make_post(client, auth_headers(token_a)).get_json()["post"]["post_id"]

    response = client.delete(f"/api/posts/{post_id}", headers=auth_headers(token_b))
    assert response.status_code == 403


def test_tc21b_unauthorized_comment_deletion(client, user_a, user_b):
    """TC-21: Bob cannot delete Alice's comment."""
    token_a, _ = user_a
    token_b, _ = user_b

    post_id = make_post(client, auth_headers(token_a)).get_json()["post"]["post_id"]

    comment_id = client.post(
        f"/api/posts/{post_id}/comments",
        json={"content": "Alice's comment"},
        headers=auth_headers(token_a),
    ).get_json()["comment"]["comment_id"]

    response = client.delete(f"/api/comments/{comment_id}", headers=auth_headers(token_b))
    assert response.status_code == 403


def test_owner_can_delete_own_post(client, user_a):
    token, _ = user_a
    headers = auth_headers(token)
    post_id = make_post(client, headers).get_json()["post"]["post_id"]

    assert client.delete(f"/api/posts/{post_id}", headers=headers).status_code == 200
    assert client.get(f"/api/posts/{post_id}").status_code == 404


def test_tc13_file_upload(client, user_a):
    """TC-13: A valid image uploads successfully."""
    token, _ = user_a
    data = {
        "file": (io.BytesIO(b"\x89PNG\r\n\x1a\n fake image bytes"), "proof.png"),
        "folder": "posts",
        "is_public": "true",
    }
    response = client.post(
        "/api/files/upload",
        data=data,
        content_type="multipart/form-data",
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    file = response.get_json()["file"]
    assert file["storage_key"].startswith("users/")
    assert file["is_public"] == 1


def test_tc14_invalid_file_type_rejected(client, user_a):
    """TC-14: A disallowed extension is rejected with 415."""
    token, _ = user_a
    data = {"file": (io.BytesIO(b"malicious"), "exploit.exe")}
    response = client.post(
        "/api/files/upload",
        data=data,
        content_type="multipart/form-data",
        headers=auth_headers(token),
    )
    assert response.status_code == 415


def test_private_file_blocked_for_other_users(client, user_a, user_b):
    """A private file cannot be downloaded by another user."""
    token_a, _ = user_a
    token_b, _ = user_b

    data = {"file": (io.BytesIO(b"secret"), "private.png"), "folder": "misc"}
    upload = client.post(
        "/api/files/upload",
        data=data,
        content_type="multipart/form-data",
        headers=auth_headers(token_a),
    ).get_json()["file"]

    response = client.get(
        f"/api/files/raw/{upload['storage_key']}",
        headers=auth_headers(token_b),
    )
    assert response.status_code == 403


def test_follow_and_following_feed(client, user_a, user_b):
    """Optional follow system: the following-scope feed filters correctly."""
    token_a, user_a_data = user_a
    token_b, _ = user_b

    make_post(client, auth_headers(token_a), "Alice's post")

    # Bob follows Alice
    follow = client.post(
        f"/api/users/{user_a_data['username']}/follow",
        headers=auth_headers(token_b),
    )
    assert follow.status_code == 200

    feed = client.get("/api/feed?scope=following", headers=auth_headers(token_b)).get_json()
    assert feed["total"] == 1
    assert feed["posts"][0]["content"] == "Alice's post"


def test_cannot_follow_self(client, user_a):
    token, user = user_a
    response = client.post(
        f"/api/users/{user['username']}/follow",
        headers=auth_headers(token),
    )
    assert response.status_code == 400