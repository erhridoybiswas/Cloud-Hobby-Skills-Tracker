"""
Skill (hobby) routes.

POST   /api/skills
GET    /api/skills
GET    /api/skills/<skill_id>
PUT    /api/skills/<skill_id>
DELETE /api/skills/<skill_id>

Authorization rule: every read/write is scoped to g.user_id. A user can
never see or modify another user's skill, even by guessing the ID.
"""
from __future__ import annotations

from flask import Blueprint, g, request

from analytics.progress_service import calculate_progress, now_iso, today_iso
from backend.middleware.auth_middleware import require_auth
from backend.utils.ids import new_id
from backend.utils.responses import created, error, forbidden, not_found, ok
from backend.utils.validators import validate_skill
from cloud.database_service import execute, query_all, query_one

skills_bp = Blueprint("skills", __name__, url_prefix="/api")


def _owned_skill_or_none(skill_id: str, user_id: str):
    return query_one(
        "SELECT * FROM skills WHERE skill_id = ? AND user_id = ?",
        (skill_id, user_id),
    )


def _decorate(skill: dict) -> dict:
    """Attach computed fields the frontend needs."""
    goal = query_one(
        """
        SELECT COALESCE(SUM(target_value), 0)  AS target_total,
               COALESCE(SUM(current_value), 0) AS current_total
        FROM goals WHERE skill_id = ? AND status != 'PAUSED'
        """,
        (skill["skill_id"],),
    )
    total_minutes = query_one(
        "SELECT COALESCE(SUM(duration_minutes), 0) AS minutes FROM practice_sessions WHERE skill_id = ?",
        (skill["skill_id"],),
    )
    skill["total_practice_minutes"] = int(total_minutes["minutes"] or 0)
    skill["total_practice_hours"] = round(skill["total_practice_minutes"] / 60, 2)
    skill["progress_percent"] = calculate_progress(
        float(goal["current_total"] or 0), float(goal["target_total"] or 0)
    )
    return skill


# ---------------------------------------------------------------------
@skills_bp.post("/skills")
@require_auth
def create_skill():
    """
    Create a hobby/skill.

    Request : {"skill_name","category","current_level","target_level",
               "start_date","target_date","description"}
    Response: 201 {"skill": {...}}
    """
    payload = request.get_json(silent=True) or {}
    cleaned, errors = validate_skill(payload)
    if errors:
        return error("Validation failed.", 400, details=errors)

    # Duplicate skill name for the same user is confusing — block it.
    if query_one(
        "SELECT 1 AS x FROM skills WHERE user_id = ? AND LOWER(skill_name) = LOWER(?)",
        (g.user_id, cleaned["skill_name"]),
    ):
        return error("You already track a skill with this name.", 409)

    skill_id = new_id("skill")
    execute(
        """
        INSERT INTO skills (skill_id, user_id, skill_name, category,
                            current_level, target_level, start_date, target_date,
                            status, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            skill_id,
            g.user_id,
            cleaned["skill_name"],
            cleaned.get("category", "Other"),
            cleaned.get("current_level", "BEGINNER"),
            cleaned.get("target_level", "INTERMEDIATE"),
            cleaned.get("start_date") or today_iso(),
            cleaned.get("target_date") or None,
            cleaned.get("status", "ACTIVE"),
            cleaned.get("description", ""),
            now_iso(),
        ),
    )

    skill = query_one("SELECT * FROM skills WHERE skill_id = ?", (skill_id,))
    return created({"skill": _decorate(skill)})


# ---------------------------------------------------------------------
@skills_bp.get("/skills")
@require_auth
def list_skills():
    """List the authenticated user's skills. Optional ?status= and ?category= filters."""
    filters = ["user_id = ?"]
    params: list = [g.user_id]

    status = (request.args.get("status") or "").strip().upper()
    if status:
        filters.append("status = ?")
        params.append(status)

    category = (request.args.get("category") or "").strip()
    if category:
        filters.append("category = ?")
        params.append(category)

    where = " AND ".join(filters)
    rows = query_all(
        f"SELECT * FROM skills WHERE {where} ORDER BY created_at DESC",
        params,
    )
    return ok({"skills": [_decorate(row) for row in rows], "count": len(rows)})


# ---------------------------------------------------------------------
@skills_bp.get("/skills/<skill_id>")
@require_auth
def get_skill(skill_id: str):
    """Skill detail + its goals (with milestones) + recent practice sessions."""
    skill = query_one("SELECT * FROM skills WHERE skill_id = ?", (skill_id,))
    if not skill:
        return not_found("Skill")
    if skill["user_id"] != g.user_id:
        return forbidden("This skill belongs to another user.")

    goals = query_all(
        "SELECT * FROM goals WHERE skill_id = ? ORDER BY created_at DESC",
        (skill_id,),
    )
    for goal in goals:
        goal["progress_percent"] = calculate_progress(goal["current_value"], goal["target_value"])
        goal["milestones"] = query_all(
            "SELECT * FROM milestones WHERE goal_id = ? ORDER BY target_value ASC",
            (goal["goal_id"],),
        )

    sessions = query_all(
        """
        SELECT * FROM practice_sessions
        WHERE skill_id = ? AND user_id = ?
        ORDER BY practiced_at DESC, created_at DESC
        LIMIT 20
        """,
        (skill_id, g.user_id),
    )

    return ok({"skill": _decorate(skill), "goals": goals, "recent_sessions": sessions})


# ---------------------------------------------------------------------
@skills_bp.put("/skills/<skill_id>")
@require_auth
def update_skill(skill_id: str):
    """Partially update a skill the caller owns."""
    if not _owned_skill_or_none(skill_id, g.user_id):
        return forbidden("Skill not found or not owned by you.")

    payload = request.get_json(silent=True) or {}
    cleaned, errors = validate_skill(payload, partial=True)
    if errors:
        return error("Validation failed.", 400, details=errors)
    if not cleaned:
        return error("No updatable fields were provided.", 400)

    set_clause = ", ".join(f"{column} = ?" for column in cleaned)
    execute(
        f"UPDATE skills SET {set_clause} WHERE skill_id = ? AND user_id = ?",
        (*cleaned.values(), skill_id, g.user_id),
    )

    skill = query_one("SELECT * FROM skills WHERE skill_id = ?", (skill_id,))
    return ok({"skill": _decorate(skill)})


# ---------------------------------------------------------------------
@skills_bp.delete("/skills/<skill_id>")
@require_auth
def delete_skill(skill_id: str):
    """
    Delete a skill.

    The `AND user_id = ?` in the WHERE clause is the authorization check:
    if the skill belongs to someone else, rowcount is 0 and we return 403.
    ON DELETE CASCADE removes its goals, milestones and practice sessions.
    """
    affected = execute(
        "DELETE FROM skills WHERE skill_id = ? AND user_id = ?",
        (skill_id, g.user_id),
    )
    if affected == 0:
        return forbidden("Skill not found or not owned by you.")
    return ok({"message": "Skill and all related data were deleted."})