"""
Practice session routes.

POST /api/practice
GET  /api/practice
GET  /api/skills/<skill_id>/practice

Logging a session is the "write path" that drives the whole analytics
system. In one transaction it:
  1. inserts the session row,
  2. increments every ACTIVE goal attached to that skill (unit-aware),
  3. marks milestones as achieved,
  4. flips goals to COMPLETED when the target is reached.
"""
from __future__ import annotations

from flask import Blueprint, g, request

from analytics.progress_service import now_iso, today_iso
from backend.middleware.auth_middleware import require_auth
from backend.utils.ids import new_id
from backend.utils.responses import created, error, forbidden, not_found, ok
from backend.utils.validators import validate_practice
from cloud.database_service import execute, query_all, query_one, run_in_transaction

practice_bp = Blueprint("practice", __name__, url_prefix="/api")


def _goal_delta(unit: str, duration_minutes: int) -> float:
    """Convert a session's minutes into the goal's own unit."""
    if unit == "minutes":
        return float(duration_minutes)
    if unit == "hours":
        return round(duration_minutes / 60.0, 2)
    if unit == "sessions":
        return 1.0
    return 0.0


# ---------------------------------------------------------------------
@practice_bp.post("/practice")
@require_auth
def log_practice():
    """
    Record a practice session.

    Request:
      {"skill_id","duration_minutes","activity","notes","practiced_at"}
    Response: 201 {"session", "updated_goals", "new_milestones"}
    """
    payload = request.get_json(silent=True) or {}
    cleaned, errors = validate_practice(payload)
    if errors:
        return error("Validation failed.", 400, details=errors)

    skill = query_one(
        "SELECT * FROM skills WHERE skill_id = ? AND user_id = ?",
        (cleaned["skill_id"], g.user_id),
    )
    if not skill:
        return forbidden("Skill not found or not owned by you.")

    session_id = new_id("session")
    practiced_at = cleaned.get("practiced_at") or today_iso()

    statements = [
        (
            """
            INSERT INTO practice_sessions (session_id, user_id, skill_id,
                                           duration_minutes, activity, notes,
                                           practiced_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id, g.user_id, cleaned["skill_id"],
                cleaned["duration_minutes"], cleaned.get("activity", ""),
                cleaned.get("notes", ""), practiced_at, now_iso(),
            ),
        )
    ]

    # ---- Cascade into goals ----------------------------------------
    active_goals = query_all(
        "SELECT * FROM goals WHERE skill_id = ? AND user_id = ? AND status = 'ACTIVE'",
        (cleaned["skill_id"], g.user_id),
    )

    new_milestones: list[dict] = []

    for goal in active_goals:
        delta = _goal_delta(goal["unit"], cleaned["duration_minutes"])
        new_value = round(float(goal["current_value"] or 0) + delta, 2)
        target = float(goal["target_value"] or 0)

        completed = target > 0 and new_value >= target
        new_status = "COMPLETED" if completed else "ACTIVE"

        statements.append(
            (
                "UPDATE goals SET current_value = ?, status = ? WHERE goal_id = ?",
                (new_value, new_status, goal["goal_id"]),
            )
        )

        # Achieve any milestone the new value has passed
        pending = query_all(
            """
            SELECT * FROM milestones
            WHERE goal_id = ? AND achieved = 0 AND target_value <= ?
            """,
            (goal["goal_id"], new_value),
        )
        for milestone in pending:
            statements.append(
                (
                    "UPDATE milestones SET achieved = 1, achieved_at = ? WHERE milestone_id = ?",
                    (now_iso(), milestone["milestone_id"]),
                )
            )
            new_milestones.append(
                {
                    "milestone_id": milestone["milestone_id"],
                    "goal_id": goal["goal_id"],
                    "goal_title": goal["title"],
                    "title": milestone["title"],
                    "target_value": milestone["target_value"],
                }
            )

    run_in_transaction(statements)

    session = query_one("SELECT * FROM practice_sessions WHERE session_id = ?", (session_id,))
    updated_goals = query_all(
        "SELECT * FROM goals WHERE skill_id = ? AND user_id = ? ORDER BY created_at DESC",
        (cleaned["skill_id"], g.user_id),
    )

    return created(
        {
            "session": session,
            "updated_goals": updated_goals,
            "new_milestones": new_milestones,
        }
    )


# ---------------------------------------------------------------------
@practice_bp.get("/practice")
@require_auth
def list_practice():
    """List the caller's practice sessions. Optional ?skill_id= and ?days=."""
    filters = ["p.user_id = ?"]
    params: list = [g.user_id]

    skill_id = (request.args.get("skill_id") or "").strip()
    if skill_id:
        filters.append("p.skill_id = ?")
        params.append(skill_id)

    days = request.args.get("days")
    if days and days.isdigit():
        filters.append("p.practiced_at >= date('now', ?)")
        params.append(f"-{int(days)} days")

    rows = query_all(
        f"""
        SELECT p.*, s.skill_name, s.category
        FROM practice_sessions p
        JOIN skills s ON s.skill_id = p.skill_id
        WHERE {' AND '.join(filters)}
        ORDER BY p.practiced_at DESC, p.created_at DESC
        LIMIT 200
        """,
        params,
    )
    return ok({"sessions": rows, "count": len(rows)})


# ---------------------------------------------------------------------
@practice_bp.get("/skills/<skill_id>/practice")
@require_auth
def list_practice_for_skill(skill_id: str):
    skill = query_one(
        "SELECT 1 AS x FROM skills WHERE skill_id = ? AND user_id = ?",
        (skill_id, g.user_id),
    )
    if not skill:
        return forbidden("Skill not found or not owned by you.")

    rows = query_all(
        """
        SELECT * FROM practice_sessions
        WHERE skill_id = ? AND user_id = ?
        ORDER BY practiced_at DESC, created_at DESC
        """,
        (skill_id, g.user_id),
    )
    return ok({"sessions": rows, "count": len(rows)})