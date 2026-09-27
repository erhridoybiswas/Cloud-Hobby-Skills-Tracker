"""
Goal & milestone routes.

POST /api/goals
GET  /api/goals
PUT  /api/goals/<goal_id>

A goal is always attached to a skill the user owns. Creating a goal with
its milestones is done inside a single transaction so a partial write can
never leave orphaned milestones behind.
"""
from __future__ import annotations

from flask import Blueprint, g, request

from analytics.progress_service import calculate_progress, goal_status, now_iso
from backend.middleware.auth_middleware import require_auth
from backend.utils.ids import new_id
from backend.utils.responses import created, error, forbidden, not_found, ok
from backend.utils.validators import GOAL_STATUSES, validate_goal
from cloud.database_service import execute, query_all, query_one, run_in_transaction

goals_bp = Blueprint("goals", __name__, url_prefix="/api")


def _decorate(goal: dict) -> dict:
    goal["progress_percent"] = calculate_progress(goal["current_value"], goal["target_value"])
    goal["status"] = goal_status(
        float(goal["current_value"] or 0),
        float(goal["target_value"] or 0),
        goal["status"],
    )
    goal["milestones"] = query_all(
        "SELECT * FROM milestones WHERE goal_id = ? ORDER BY target_value ASC",
        (goal["goal_id"],),
    )
    return goal


# ---------------------------------------------------------------------
@goals_bp.post("/goals")
@require_auth
def create_goal():
    """
    Create a goal (optionally with milestones) for one of the user's skills.

    Request:
      {
        "skill_id": "skl_...",
        "title": "Practice 30 hours",
        "target_value": 30,
        "unit": "hours",
        "deadline": "2025-12-31",
        "milestones": [{"title": "5 hours", "target_value": 5}, ...]
      }
    Response: 201 {"goal": {...}}
    """
    payload = request.get_json(silent=True) or {}
    cleaned, errors = validate_goal(payload)
    if errors:
        return error("Validation failed.", 400, details=errors)

    skill_id = (payload.get("skill_id") or "").strip()
    skill = query_one(
        "SELECT * FROM skills WHERE skill_id = ? AND user_id = ?",
        (skill_id, g.user_id),
    )
    if not skill:
        return forbidden("Skill not found or not owned by you.")

    goal_id = new_id("goal")
    statements = [
        (
            """
            INSERT INTO goals (goal_id, user_id, skill_id, title, target_value,
                               current_value, unit, deadline, status, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'ACTIVE', ?)
            """,
            (
                goal_id, g.user_id, skill_id, cleaned["title"],
                cleaned["target_value"], cleaned["unit"],
                cleaned.get("deadline") or None, now_iso(),
            ),
        )
    ]

    raw_milestones = payload.get("milestones") or []
    if isinstance(raw_milestones, list):
        for index, item in enumerate(raw_milestones[:20], start=1):
            if not isinstance(item, dict):
                continue
            try:
                target = float(item.get("target_value"))
            except (TypeError, ValueError):
                continue
            if target <= 0 or target > cleaned["target_value"]:
                continue
            title = str(item.get("title") or f"Milestone {index}").strip()[:120]
            statements.append(
                (
                    """
                    INSERT INTO milestones (milestone_id, goal_id, title,
                                            target_value, achieved, achieved_at)
                    VALUES (?, ?, ?, ?, 0, NULL)
                    """,
                    (new_id("milestone"), goal_id, title, target),
                )
            )

    # Atomic: either the goal AND all milestones are saved, or nothing is.
    run_in_transaction(statements)

    goal = query_one("SELECT * FROM goals WHERE goal_id = ?", (goal_id,))
    return created({"goal": _decorate(goal)})


# ---------------------------------------------------------------------
@goals_bp.get("/goals")
@require_auth
def list_goals():
    """List the caller's goals. Optional ?status=ACTIVE|COMPLETED|PAUSED."""
    filters = ["g.user_id = ?"]
    params: list = [g.user_id]

    status = (request.args.get("status") or "").strip().upper()
    if status:
        filters.append("g.status = ?")
        params.append(status)

    rows = query_all(
        f"""
        SELECT g.*, s.skill_name, s.category
        FROM goals g
        JOIN skills s ON s.skill_id = g.skill_id
        WHERE {' AND '.join(filters)}
        ORDER BY g.created_at DESC
        """,
        params,
    )
    return ok({"goals": [_decorate(row) for row in rows], "count": len(rows)})


# ---------------------------------------------------------------------
@goals_bp.put("/goals/<goal_id>")
@require_auth
def update_goal(goal_id: str):
    """
    Update a goal's title, target, deadline, or status.

    `current_value` is intentionally NOT client-writable — it is derived
    from practice sessions. Letting a client set it would make progress
    meaningless (and trivially cheatable).
    """
    goal = query_one(
        "SELECT * FROM goals WHERE goal_id = ? AND user_id = ?",
        (goal_id, g.user_id),
    )
    if not goal:
        return forbidden("Goal not found or not owned by you.")

    payload = request.get_json(silent=True) or {}
    updates: dict = {}
    errors: dict[str, str] = {}

    if "title" in payload:
        title = str(payload.get("title") or "").strip()[:120]
        if not title:
            errors["title"] = "Title cannot be empty."
        else:
            updates["title"] = title

    if "target_value" in payload:
        try:
            target = float(payload["target_value"])
            if target <= 0:
                raise ValueError
            updates["target_value"] = target
        except (TypeError, ValueError):
            errors["target_value"] = "Target value must be a positive number."

    if "deadline" in payload:
        updates["deadline"] = str(payload.get("deadline") or "").strip()[:10] or None

    if "status" in payload:
        status = str(payload.get("status") or "").strip().upper()
        if status not in GOAL_STATUSES:
            errors["status"] = f"Status must be one of {sorted(GOAL_STATUSES)}."
        else:
            updates["status"] = status

    if errors:
        return error("Validation failed.", 400, details=errors)
    if not updates:
        return error("No updatable fields were provided.", 400)

    set_clause = ", ".join(f"{column} = ?" for column in updates)
    execute(
        f"UPDATE goals SET {set_clause} WHERE goal_id = ? AND user_id = ?",
        (*updates.values(), goal_id, g.user_id),
    )

    refreshed = query_one("SELECT * FROM goals WHERE goal_id = ?", (goal_id,))
    return ok({"goal": _decorate(refreshed)})