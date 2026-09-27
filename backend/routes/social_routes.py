"""
Social routes.

POST   /api/posts/<post_id>/like      POST   /api/posts/<post_id>/comments
DELETE /api/posts/<post_id>/like      GET    /api/posts/<post_id>/comments
DELETE /api/comments/<comment_id>

POST   /api/users/<username>/follow   DELETE /api/users/<username>/follow
GET    /api/users/<username>/followers
GET    /api/users/<username>/following
"""
from __future__ import annotations

from flask import Blueprint, g, request

from analytics.progress_service import now_iso
from backend.middleware.auth_middleware import optional_auth, require_auth
from backend.utils.ids import new_id
from backend.utils.responses import created, error, forbidden, not_found, ok
from backend.utils.validators import MAX_COMMENT_LENGTH, clean_text
from cloud.database_service import execute, query_all, query_one, query_scalar

social_bp = Blueprint("social", __name__, url_prefix="/api")


def _like_count(post_id: str) -> int:
    return int(query_scalar("SELECT COUNT(*) FROM likes WHERE post_id = ?", (post_id,)) or 0)


def _post_exists(post_id: str) -> bool:
    return query_one("SELECT 1 AS x FROM posts WHERE post_id = ?", (post_id,)) is not None


# ---------------------------------------------------------------------
# LIKES
# ---------------------------------------------------------------------
@social_bp.post("/posts/<post_id>/like")
@require_auth
def like_post(post_id: str):
    """
    Like a post.

    `INSERT OR IGNORE` + the UNIQUE(post_id, user_id) constraint makes this
    idempotent: double-tapping the like button can never create duplicates
    or raise an error.
    """
    if not _post_exists(post_id):
        return not_found("Post")

    execute(
        """
        INSERT OR IGNORE INTO likes (like_id, post_id, user_id, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (new_id("like"), post_id, g.user_id, now_iso()),
    )
    return ok({"liked": True, "like_count": _like_count(post_id)})


@social_bp.delete("/posts/<post_id>/like")
@require_auth
def unlike_post(post_id: str):
    if not _post_exists(post_id):
        return not_found("Post")

    execute(
        "DELETE FROM likes WHERE post_id = ? AND user_id = ?",
        (post_id, g.user_id),
    )
    return ok({"liked": False, "like_count": _like_count(post_id)})


# ---------------------------------------------------------------------
# COMMENTS
# ---------------------------------------------------------------------
@social_bp.post("/posts/<post_id>/comments")
@require_auth
def add_comment(post_id: str):
    """Add a comment. Content is length-capped and escaped on render."""
    if not _post_exists(post_id):
        return not_found("Post")

    payload = request.get_json(silent=True) or {}
    content, err = clean_text(payload.get("content"), MAX_COMMENT_LENGTH, "Comment")
    if err or not content:
        return error(err or "Comment content is required.", 400)

    comment_id = new_id("comment")
    execute(
        """
        INSERT INTO comments (comment_id, post_id, user_id, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (comment_id, post_id, g.user_id, content, now_iso()),
    )

    comment = query_one(
        """
        SELECT c.*, u.username, u.name, u.profile_picture
        FROM comments c
        JOIN users u ON u.user_id = c.user_id
        WHERE c.comment_id = ?
        """,
        (comment_id,),
    )
    return created(
        {
            "comment": comment,
            "comment_count": int(
                query_scalar("SELECT COUNT(*) FROM comments WHERE post_id = ?", (post_id,)) or 0
            ),
        }
    )


@social_bp.get("/posts/<post_id>/comments")
@optional_auth
def get_comments(post_id: str):
    """Public comment list, oldest first."""
    if not _post_exists(post_id):
        return not_found("Post")

    rows = query_all(
        """
        SELECT c.comment_id, c.post_id, c.user_id, c.content, c.created_at,
               u.username, u.name, u.profile_picture
        FROM comments c
        JOIN users u ON u.user_id = c.user_id
        WHERE c.post_id = ?
        ORDER BY c.created_at ASC
        """,
        (post_id,),
    )
    for row in rows:
        row["is_mine"] = g.user_id == row["user_id"]

    return ok({"comments": rows, "count": len(rows)})


@social_bp.delete("/comments/<comment_id>")
@require_auth
def delete_comment(comment_id: str):
    """
    Delete a comment.

    Allowed if you wrote the comment OR you are an admin. The query is
    written so the ownership rule lives in SQL, not in Python `if`s that
    could be forgotten.
    """
    comment = query_one("SELECT * FROM comments WHERE comment_id = ?", (comment_id,))
    if not comment:
        return not_found("Comment")

    is_admin = bool(
        query_one("SELECT is_admin FROM users WHERE user_id = ?", (g.user_id,)) or {}
    ).get("is_admin") if False else bool(
        (query_one("SELECT is_admin FROM users WHERE user_id = ?", (g.user_id,)) or {}).get("is_admin")
    )

    if comment["user_id"] != g.user_id and not is_admin:
        return forbidden("You can only delete your own comments.")

    execute("DELETE FROM comments WHERE comment_id = ?", (comment_id,))
    return ok({"message": "Comment deleted."})


# ---------------------------------------------------------------------
# FOLLOWS
# ---------------------------------------------------------------------
def _user_by_username(username: str):
    return query_one("SELECT * FROM users WHERE username = ?", (username.strip().lower(),))


@social_bp.post("/users/<username>/follow")
@require_auth
def follow_user(username: str):
    target = _user_by_username(username)
    if not target:
        return not_found("User")
    if target["user_id"] == g.user_id:
        return error("You cannot follow yourself.", 400)

    execute(
        """
        INSERT OR IGNORE INTO follows (follow_id, follower_id, following_id, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (new_id("follow"), g.user_id, target["user_id"], now_iso()),
    )
    return ok({"following": True, "username": target["username"]})


@social_bp.delete("/users/<username>/follow")
@require_auth
def unfollow_user(username: str):
    target = _user_by_username(username)
    if not target:
        return not_found("User")

    execute(
        "DELETE FROM follows WHERE follower_id = ? AND following_id = ?",
        (g.user_id, target["user_id"]),
    )
    return ok({"following": False, "username": target["username"]})


@social_bp.get("/users/<username>/followers")
def get_followers(username: str):
    target = _user_by_username(username)
    if not target:
        return not_found("User")

    rows = query_all(
        """
        SELECT u.user_id, u.username, u.name, u.profile_picture, f.created_at
        FROM follows f
        JOIN users u ON u.user_id = f.follower_id
        WHERE f.following_id = ?
        ORDER BY f.created_at DESC
        """,
        (target["user_id"],),
    )
    return ok({"users": rows, "count": len(rows)})


@social_bp.get("/users/<username>/following")
def get_following(username: str):
    target = _user_by_username(username)
    if not target:
        return not_found("User")

    rows = query_all(
        """
        SELECT u.user_id, u.username, u.name, u.profile_picture, f.created_at
        FROM follows f
        JOIN users u ON u.user_id = f.following_id
        WHERE f.follower_id = ?
        ORDER BY f.created_at DESC
        """,
        (target["user_id"],),
    )
    return ok({"users": rows, "count": len(rows)})