"""
Analytics routes.

GET /api/analytics/dashboard

One request returns everything the dashboard needs: summary KPIs, five
chart datasets, and recent activity. Doing it in one round-trip keeps the
UI snappy and reduces load on the database.
"""
from __future__ import annotations

from flask import Blueprint, g

from analytics import progress_service as ps
from backend.middleware.auth_middleware import require_auth
from backend.utils.responses import ok
from cloud.database_service import query_all, query_scalar

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api")


@analytics_bp.get("/analytics/dashboard")
@require_auth
def dashboard():
    """Return the full personal analytics payload."""

    user_id = g.user_id

    skills = query_all("SELECT * FROM skills WHERE user_id = ?", (user_id,))
    sessions = query_all(
        "SELECT * FROM practice_sessions WHERE user_id = ?",
        (user_id,),
    )
    goals = query_all("SELECT * FROM goals WHERE user_id = ?", (user_id,))

    # ---------------- Summary KPIs ----------------
    total_minutes = ps.total_minutes(sessions)
    practice_dates = [s["practiced_at"] for s in sessions]

    milestone_rows = query_all(
        """
        SELECT m.*, gol.title AS goal_title
        FROM milestones m
        JOIN goals gol ON gol.goal_id = m.goal_id
        WHERE gol.user_id = ?
        ORDER BY m.achieved_at DESC
        """,
        (user_id,),
    )

    completion = ps.goal_completion_breakdown(goals)
    top_skill = ps.most_practiced_skill(sessions, skills)

    summary = {
        "total_practice_minutes": total_minutes,
        "total_practice_hours": ps.minutes_to_hours(total_minutes),
        "weekly_practice_hours": ps.minutes_to_hours(ps.minutes_since(sessions, 7)),
        "monthly_practice_hours": ps.minutes_to_hours(ps.minutes_in_current_month(sessions)),
        "most_practiced_skill": top_skill,
        "current_streak": ps.current_streak(practice_dates),
        "longest_streak": ps.longest_streak(practice_dates),
        "active_skills": sum(1 for s in skills if s["status"] == "ACTIVE"),
        "total_skills": len(skills),
        "goals_completed": completion["completed"],
        "active_goals": completion["active"],
        "paused_goals": completion["paused"],
        "milestones_achieved": sum(1 for m in milestone_rows if m["achieved"]),
        "milestones_total": len(milestone_rows),
        "posts_count": query_scalar("SELECT COUNT(*) FROM posts WHERE user_id = ?", (user_id,)),
        "likes_received": query_scalar(
            """
            SELECT COUNT(*) FROM likes l
            JOIN posts p ON p.post_id = l.post_id
            WHERE p.user_id = ?
            """,
            (user_id,),
        ),
        "comments_received": query_scalar(
            """
            SELECT COUNT(*) FROM comments c
            JOIN posts p ON p.post_id = c.post_id
            WHERE p.user_id = ?
            """,
            (user_id,),
        ),
    }

    # ---------------- Chart datasets ----------------
    charts = {
        "practice_by_skill": ps.practice_by_skill(sessions, skills),
        "weekly_trend": ps.weekly_trend(sessions, weeks=6),
        "monthly_trend": ps.monthly_trend(sessions, months=6),
        "goal_completion": {
            "labels": ["Completed", "Active", "Paused"],
            "values": [completion["completed"], completion["active"], completion["paused"]],
        },
        "skill_distribution": ps.skill_distribution(skills),
    }

    # ---------------- Recent activity ----------------
    recent_activity = ps.recent_activity(sessions, skills, limit=8)
    recent_achievements = [
        {
            "milestone_id": m["milestone_id"],
            "title": m["title"],
            "goal_title": m["goal_title"],
            "achieved_at": m["achieved_at"],
        }
        for m in milestone_rows
        if m["achieved"]
    ][:5]

    return ok(
        {
            "summary": summary,
            "charts": charts,
            "recent_activity": recent_activity,
            "recent_achievements": recent_achievements,
        }
    )


@analytics_bp.get("/community/trending")
def trending_skills():
    """Top skills mentioned in community posts over the last 30 days."""
    rows = query_all(
        """
        SELECT s.skill_name, s.category, COUNT(*) AS post_count
        FROM posts p
        JOIN skills s ON s.skill_id = p.skill_id
        WHERE p.created_at >= datetime('now', '-30 days')
        GROUP BY s.skill_name, s.category
        ORDER BY post_count DESC
        LIMIT 8
        """
    )
    return ok({"trending": rows})