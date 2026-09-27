"""
Community post routes.

POST   /api/posts
GET    /api/feed
GET    /api/posts/<post_id>
DELETE /api/posts/<post_id>

The feed endpoint is the most performance-sensitive query in the app.
It is built dynamically so filters compose cleanly, but every *value* is
still bound as a parameter — the SQL string only ever contains a fixed
allow-list of fragments.
"""
from __future__ import annotations

from flask import Blueprint, g, request

from analytics.progress_service import now_iso
from backend.middleware.auth_middleware import optional_auth, require_auth
from backend.utils.ids import new_id
from backend.utils.responses import created, error, forbidden, not_found, ok
from backend.utils.validators import MAX_POST_LENGTH, clean_text
from cloud.database_service import execute, query_all, query_one, query_scalar

posts_bp = Blueprint("posts", __name__, url_prefix="/api")

SORT_OPTIONS = {"recent": "p.created_at DESC", "liked": "like_count DESC, p.created_at DESC"}


def _serialise(row: dict, viewer_id: str | None) -> dict:
    return {
        "post_id": row["post_id"],
        "content": row["content"],
        "media_url": row.get("media_url"),
        "created_at": row["created_at"],
        "author": {
            "user_id": row["user_id"],
            "username": row["username"],
            "name": row["name"],
            "profile_picture": row.get("profile_picture"),
        },
        "skill": (
            {
                "skill_id": row["skill_id"],
                "skill_name": row["skill_name"],
                "category": row["category"],
            }
            if row.get("skill_id")
            else None
        ),
        "like_count": int(row.get("like_count") or 0),
        "comment_count": int(row.get("comment_count") or 0),
        "liked_by_me": bool(row.get("liked_by_me")),
        "is_mine": viewer_id == row["user_id"],
    }


# ---------------------------------------------------------------------
@posts_bp.post("/posts")
@require_auth
def create_post():
    """
    Share an achievement with the community.

    Request : {"content","skill_id"?, "media_url"?}
    Response: 201 {"post": {...}}
    """
    payload = request.get_json(silent=True) or {}

    content, err = clean_text(payload.get("content"), MAX_POST_LENGTH, "Post content")
    if err or not content:
        return error(err or "Post content is required.", 400)

    skill_id = (payload.get("skill_id") or "").strip() or None
    if skill_id:
        owned = query_one(
            "SELECT 1 AS x FROM skills WHERE skill_id = ? AND user_id = ?",
            (skill_id, g.user_id),
        )
        if not owned:
            return forbidden("You can only tag your own skills.")
    else:
        skill_id = None

    media_url, err = clean_text(payload.get("media_url"), 500, "Media URL")
    if err:
        return error(err, 400)

    post_id = new_id("post")
    execute(
        """
        INSERT INTO posts (post_id, user_id, skill_id, content, media_url, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (post_id, g.user_id, skill_id, content, media_url or None, now_iso()),
    )

    row = query_one(
        """
        SELECT p.*, u.username, u.name, u.profile_picture,
               s.skill_name, s.category
        FROM posts p
        JOIN users u ON u.user_id = p.user_id
        LEFT JOIN skills s ON s.skill_id = p.skill_id
        WHERE p.post_id = ?
        """,
        (post_id,),
    )
    row["like_count"] = 0
    row["comment_count"] = 0
    row["liked_by_me"] = 0
    return created({"post": _serialise(row, g.user_id)})


# ---------------------------------------------------------------------
@posts_bp.get("/feed")
@optional_auth
def get_feed():
    """
    Community feed with filtering, sorting and pagination.

    Query params:
      scope    = all | following       (default: all)
      category = Photography, Music, ...
      sort     = recent | liked        (default: recent)
      q        = free-text search in post content or skill name
      page     = 1-based               (default: 1)
      limit    = max 50                (default: 20)
    """
    viewer_id = g.user_id

    scope = (request.args.get("scope") or "all").lower()
    category = (request.args.get("category") or "").strip()
    sort = (request.args.get("sort") or "recent").lower()
    search = (request.args.get("q") or "").strip()

    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        limit = min(50, max(1, int(request.args.get("limit", 20))))
    except ValueError:
        limit = 20

    order_by = SORT_OPTIONS.get(sort, SORT_OPTIONS["recent"])

    where = ["1 = 1"]
    params: list = [viewer_id or ""]

    if scope == "following":
        if not viewer_id:
            return error("Log in to view your following feed.", 401)
        where.append("p.user_id IN (SELECT following_id FROM follows WHERE follower_id = ?)")
        params.append(viewer_id)

    if category:
        where.append("s.category = ?")
        params.append(category)

    if search:
        where.append("(p.content LIKE ? OR s.skill_name LIKE ? OR u.username LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term, term])

    where_sql = " AND ".join(where)

    base_sql = f"""
        SELECT p.post_id, p.user_id, p.skill_id, p.content, p.media_url, p.created_at,
               u.username, u.name, u.profile_picture,
               s.skill_name, s.category,
               (SELECT COUNT(*) FROM likes    l WHERE l.post_id = p.post_id) AS like_count,
               (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.post_id) AS comment_count,
               EXISTS(SELECT 1 FROM likes l2
                      WHERE l2.post_id = p.post_id AND l2.user_id = ?) AS liked_by_me
        FROM posts p
        JOIN users u ON u.user_id = p.user_id
        LEFT JOIN skills s ON s.skill_id = p.skill_id
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
    """

    rows = query_all(base_sql, params + [limit, (page - 1) * limit])

    total = query_scalar(
        f"""
        SELECT COUNT(*)
        FROM posts p
        JOIN users u ON u.user_id = p.user_id
        LEFT JOIN skills s ON s.skill_id = p.skill_id
        WHERE {where_sql}
        """,
        params[1:],   # drop the viewer_id used only for liked_by_me
    )

    return ok(
        {
            "posts": [_serialise(row, viewer_id) for row in rows],
            "page": page,
            "limit": limit,
            "total": int(total or 0),
        }
    )


# ---------------------------------------------------------------------
@posts_bp.get("/posts/<post_id>")
@optional_auth
def get_post(post_id: str):
    row = query_one(
        """
        SELECT p.post_id, p.user_id, p.skill_id, p.content, p.media_url, p.created_at,
               u.username, u.name, u.profile_picture,
               s.skill_name, s.category,
               (SELECT COUNT(*) FROM likes    l WHERE l.post_id = p.post_id) AS like_count,
               (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.post_id) AS comment_count,
               EXISTS(SELECT 1 FROM likes l2
                      WHERE l2.post_id = p.post_id AND l2.user_id = ?) AS liked_by_me
        FROM posts p
        JOIN users u ON u.user_id = p.user_id
        LEFT JOIN skills s ON s.skill_id = p.skill_id
        WHERE p.post_id = ?
        """,
        (g.user_id or "", post_id),
    )
    if not row:
        return not_found("Post")
    return ok({"post": _serialise(row, g.user_id)})


# ---------------------------------------------------------------------
@posts_bp.delete("/posts/<post_id>")
@require_auth
def delete_post(post_id: str):
    """Delete one of your own posts (cascades to its likes and comments)."""
    affected = execute(
        "DELETE FROM posts WHERE post_id = ? AND user_id = ?",
        (post_id, g.user_id),
    )
    if affected == 0:
        return forbidden("Post not found or not owned by you.")
    return ok({"message": "Post deleted."})