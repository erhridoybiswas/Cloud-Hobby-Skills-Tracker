"""
Progress Analytics Service
==========================

Everything in this module is a PURE FUNCTION: it takes plain Python data
(lists of dicts) and returns plain Python data. No database, no Flask.

Why? Because pure functions are trivially unit-testable and reusable.
The route layer fetches rows and passes them in here.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Iterable, Optional


# ---------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------
def to_date(value) -> Optional[date]:
    """Coerce a date / datetime / ISO string into a date object."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def today_iso() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ---------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------
def calculate_progress(current_value: float, target_value: float) -> float:
    """
    progress % = min( (current / target) * 100 , 100 )

    Returns 0.0 when target is zero or negative (avoids ZeroDivisionError).
    Displayed progress is capped at 100, but the raw current_value stored
    in the database stays truthful (e.g. 34 hours against a 30-hour goal).
    """
    if not target_value or target_value <= 0:
        return 0.0
    percent = (float(current_value) / float(target_value)) * 100.0
    return round(min(percent, 100.0), 2)


def goal_status(current_value: float, target_value: float, declared_status: str) -> str:
    """Derive the real status of a goal from its numbers."""
    if declared_status == "PAUSED":
        return "PAUSED"
    if target_value > 0 and current_value >= target_value:
        return "COMPLETED"
    return "ACTIVE"


# ---------------------------------------------------------------------
# Streaks
# ---------------------------------------------------------------------
def current_streak(practice_dates: Iterable, today: Optional[date] = None) -> int:
    """
    Consecutive days (ending today or yesterday) with >= 1 practice session.

    We allow the streak to start at YESTERDAY if the user has not practiced
    yet today — otherwise every streak would visually reset at midnight.
    """
    days = {d for d in (to_date(x) for x in practice_dates) if d is not None}
    if not days:
        return 0

    today = today or date.today()
    cursor = today if today in days else today - timedelta(days=1)

    if cursor not in days:
        return 0

    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def longest_streak(practice_dates: Iterable) -> int:
    """The longest run of consecutive practice days in the whole history."""
    days = sorted({d for d in (to_date(x) for x in practice_dates) if d is not None})
    if not days:
        return 0

    best = 1
    run = 1
    for previous, current in zip(days, days[1:]):
        if (current - previous).days == 1:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


# ---------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------
def total_minutes(sessions: Iterable[dict]) -> int:
    return sum(int(s.get("duration_minutes") or 0) for s in sessions)


def minutes_to_hours(minutes: float) -> float:
    return round(float(minutes) / 60.0, 2)


def minutes_since(sessions: Iterable[dict], days: int, reference: Optional[date] = None) -> int:
    """Sum of practice minutes in the last N days (inclusive of today)."""
    reference = reference or date.today()
    cutoff = reference - timedelta(days=days - 1)
    total = 0
    for session in sessions:
        practiced = to_date(session.get("practiced_at"))
        if practiced and cutoff <= practiced <= reference:
            total += int(session.get("duration_minutes") or 0)
    return total


def minutes_in_current_month(sessions: Iterable[dict], reference: Optional[date] = None) -> int:
    reference = reference or date.today()
    total = 0
    for session in sessions:
        practiced = to_date(session.get("practiced_at"))
        if practiced and practiced.year == reference.year and practiced.month == reference.month:
            total += int(session.get("duration_minutes") or 0)
    return total


def practice_by_skill(sessions: Iterable[dict], skills: Iterable[dict]) -> list[dict]:
    """Total hours per skill, sorted descending. Used for the bar chart."""
    names = {s["skill_id"]: s["skill_name"] for s in skills}
    totals: dict[str, int] = defaultdict(int)
    for session in sessions:
        totals[session["skill_id"]] += int(session.get("duration_minutes") or 0)

    rows = [
        {"label": names.get(skill_id, "Unknown"), "value": minutes_to_hours(minutes), "minutes": minutes}
        for skill_id, minutes in totals.items()
    ]
    return sorted(rows, key=lambda r: r["minutes"], reverse=True)


def weekly_trend(sessions: Iterable[dict], weeks: int = 6, reference: Optional[date] = None) -> list[dict]:
    """
    Hours practiced per ISO week for the last N weeks (oldest first).
    Feeds the line chart on the dashboard.
    """
    reference = reference or date.today()
    this_monday = reference - timedelta(days=reference.weekday())

    buckets: dict[str, int] = {}
    labels: list[str] = []
    for offset in range(weeks - 1, -1, -1):
        monday = this_monday - timedelta(weeks=offset)
        iso_year, iso_week, _ = monday.isocalendar()
        label = f"{iso_year}-W{iso_week:02d}"
        buckets[label] = 0
        labels.append(label)

    earliest = this_monday - timedelta(weeks=weeks - 1)
    for session in sessions:
        practiced = to_date(session.get("practiced_at"))
        if not practiced or practiced < earliest:
            continue
        monday = practiced - timedelta(days=practiced.weekday())
        iso_year, iso_week, _ = monday.isocalendar()
        label = f"{iso_year}-W{iso_week:02d}"
        if label in buckets:
            buckets[label] += int(session.get("duration_minutes") or 0)

    return [{"label": label, "value": minutes_to_hours(buckets[label])} for label in labels]


def monthly_trend(sessions: Iterable[dict], months: int = 6, reference: Optional[date] = None) -> list[dict]:
    """Hours practiced per calendar month for the last N months (oldest first)."""
    reference = reference or date.today()
    buckets: dict[str, int] = {}
    labels: list[str] = []

    year, month = reference.year, reference.month
    cursor_months: list[tuple[int, int]] = []
    for _ in range(months):
        cursor_months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    cursor_months.reverse()

    for y, m in cursor_months:
        label = f"{y}-{m:02d}"
        buckets[label] = 0
        labels.append(label)

    for session in sessions:
        practiced = to_date(session.get("practiced_at"))
        if not practiced:
            continue
        label = f"{practiced.year}-{practiced.month:02d}"
        if label in buckets:
            buckets[label] += int(session.get("duration_minutes") or 0)

    return [{"label": label, "value": minutes_to_hours(buckets[label])} for label in labels]


def goal_completion_breakdown(goals: Iterable[dict]) -> dict:
    """Counts of completed / active / paused goals for the doughnut chart."""
    counts = {"completed": 0, "active": 0, "paused": 0}
    for goal in goals:
        status = goal_status(
            float(goal.get("current_value") or 0),
            float(goal.get("target_value") or 0),
            goal.get("status", "ACTIVE"),
        )
        if status == "COMPLETED":
            counts["completed"] += 1
        elif status == "PAUSED":
            counts["paused"] += 1
        else:
            counts["active"] += 1
    return counts


def skill_distribution(skills: Iterable[dict]) -> list[dict]:
    """Number of skills per category — for the pie chart."""
    counts: dict[str, int] = defaultdict(int)
    for skill in skills:
        counts[skill.get("category") or "Other"] += 1
    return [{"label": k, "value": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]


def most_practiced_skill(sessions: Iterable[dict], skills: Iterable[dict]) -> Optional[dict]:
    rows = practice_by_skill(sessions, skills)
    if not rows or rows[0]["minutes"] == 0:
        return None
    return rows[0]


def recent_activity(sessions: Iterable[dict], skills: Iterable[dict], limit: int = 8) -> list[dict]:
    """Most recent practice sessions, newest first, with skill names attached."""
    names = {s["skill_id"]: s["skill_name"] for s in skills}
    ordered = sorted(
        sessions,
        key=lambda s: (s.get("practiced_at") or "", s.get("created_at") or ""),
        reverse=True,
    )
    return [
        {
            "session_id": s["session_id"],
            "skill_name": names.get(s["skill_id"], "Unknown"),
            "duration_minutes": s["duration_minutes"],
            "activity": s.get("activity", ""),
            "practiced_at": s.get("practiced_at"),
        }
        for s in ordered[:limit]
    ]