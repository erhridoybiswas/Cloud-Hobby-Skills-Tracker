"""
Seed script — creates synthetic demo data.

Run from the project root:
    python sample_data/seed.py

Creates three users (all with password `Password123`), their skills,
goals, practice history, community posts, likes, comments and follows.

Everything here is DUMMY data. Never seed a production database.
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app import create_app  # noqa: E402
from backend.utils.ids import new_id  # noqa: E402
from cloud.auth_service import hash_password  # noqa: E402
from cloud.database_service import execute, query_all, query_one  # noqa: E402

random.seed(42)   # deterministic output for reproducible screenshots

DEMO_PASSWORD = "Password123"

USERS = [
    {
        "username": "alice",
        "name": "Alice Sharma",
        "email": "alice@example.com",
        "bio": "Learning photography and classical guitar. Based in Pune.",
        "interests": "Photography, Guitar, Chess",
    },
    {
        "username": "bob",
        "name": "Bob Mehta",
        "email": "bob@example.com",
        "bio": "Full-stack developer learning chess and cooking.",
        "interests": "Coding, Chess, Cooking",
    },
    {
        "username": "carol",
        "name": "Carol Nair",
        "email": "carol@example.com",
        "bio": "Fitness enthusiast and hobby gardener.",
        "interests": "Fitness, Gardening, Painting",
    },
]

SKILLS = [
    ("alice", "Photography", "Photography", "INTERMEDIATE", "ADVANCED",
     "Street and portrait photography with natural light."),
    ("alice", "Guitar", "Music", "BEGINNER", "INTERMEDIATE",
     "Classical guitar, working through the Carcassi studies."),
    ("bob", "Chess", "Games", "BEGINNER", "INTERMEDIATE",
     "Studying endgames and tactical patterns."),
    ("bob", "Cooking", "Cooking", "BEGINNER", "INTERMEDIATE",
     "Learning regional Indian cuisine."),
    ("carol", "Fitness", "Fitness", "INTERMEDIATE", "ADVANCED",
     "Strength training and mobility work."),
    ("carol", "Gardening", "Outdoors", "BEGINNER", "INTERMEDIATE",
     "Growing herbs and seasonal vegetables."),
]

GOALS = [
    # (username, skill_name, title, target, unit, milestones)
    ("alice", "Photography", "Practice 30 hours of photography", 30, "hours", [5, 10, 20, 30]),
    ("alice", "Guitar", "Practice 20 hours of guitar", 20, "hours", [5, 10, 20]),
    ("bob", "Chess", "Play 50 practice games", 50, "sessions", [10, 25, 50]),
    ("bob", "Cooking", "Cook 25 meals", 25, "sessions", [5, 15, 25]),
    ("carol", "Fitness", "Train 40 hours", 40, "hours", [10, 20, 40]),
]

ACTIVITIES = {
    "Photography": ["Street photography walk", "Portrait session", "Edited raw files",
                    "Studied composition", "Golden-hour shoot"],
    "Guitar": ["Practiced Carcassi study", "Chord transitions", "Fingerstyle exercise",
               "Learned a new piece", "Scale practice"],
    "Chess": ["Tactics puzzles", "Played online games", "Studied endgame theory",
              "Analysed a grandmaster game"],
    "Cooking": ["Made dal makhani", "Tried a new biryani recipe", "Baked bread",
                "Meal prep session"],
    "Fitness": ["Upper body strength", "5 km run", "Mobility and stretching",
                "Leg day", "Core workout"],
    "Gardening": ["Planted herbs", "Repotted saplings", "Weeded and watered",
                  "Pruned the rose bushes"],
}

POSTS = [
    ("alice", "Photography", "Hit the 10-hour mark in photography! Natural light portraits are finally clicking 📸"),
    ("alice", "Guitar", "Completed my first full song on guitar today 🎸 Three weeks ago I couldn't hold a barre chord."),
    ("bob", "Chess", "25 practice games done. My rating went up 180 points in a month ♟️"),
    ("bob", "Cooking", "Cooked 5 full meals from scratch this week. The biryani was a hit 🍛"),
    ("carol", "Fitness", "40 hours of training complete! Consistency really is everything 💪"),
    ("carol", "Gardening", "My herb garden is finally thriving 🌿 Mint, basil and coriander all growing."),
    ("alice", "Photography", "Pro tip I learned: shoot in the first 30 minutes after sunrise. The light is unreal."),
]

COMMENTS = [
    "This is so inspiring, congrats! 🎉",
    "Great progress — keep it up!",
    "How did you stay consistent? Any tips?",
    "Love this 🔥",
    "This motivates me to start too!",
]


def iso(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


def now_iso() -> str:
    from datetime import datetime
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def seed() -> None:
    app = create_app()

    with app.app_context():
        # ---- Idempotency check -------------------------------------
        existing = query_one("SELECT 1 AS x FROM users LIMIT 1")
        if existing:
            print("⚠️  Database already contains data.")
            print("   Delete backend/data/app.db and re-run to reseed.")
            return

        # ---- Users --------------------------------------------------
        user_ids: dict[str, str] = {}
        for spec in USERS:
            user_id = new_id("user")
            user_ids[spec["username"]] = user_id
            execute(
                """
                INSERT INTO users (user_id, name, username, email, password_hash,
                                   profile_picture, bio, interests, created_at)
                VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)
                """,
                (
                    user_id, spec["name"], spec["username"], spec["email"],
                    hash_password(DEMO_PASSWORD), spec["bio"], spec["interests"],
                    iso(60),
                ),
            )
        print(f"✅ Created {len(USERS)} users (password: {DEMO_PASSWORD})")

        # ---- Skills -------------------------------------------------
        skill_ids: dict[tuple[str, str], str] = {}
        for username, name, category, current, target, description in SKILLS:
            skill_id = new_id("skill")
            skill_ids[(username, name)] = skill_id
            execute(
                """
                INSERT INTO skills (skill_id, user_id, skill_name, category,
                                    current_level, target_level, start_date, target_date,
                                    status, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
                """,
                (
                    skill_id, user_ids[username], name, category, current, target,
                    iso(45), (date.today() + timedelta(days=90)).isoformat(),
                    description, iso(45),
                ),
            )
        print(f"✅ Created {len(SKILLS)} skills")

        # ---- Goals + milestones -------------------------------------
        goal_ids: list[tuple[str, str, float, str]] = []   # (username, goal_id, target, unit)
        milestone_count = 0

        for username, skill_name, title, target, unit, milestones in GOALS:
            goal_id = new_id("goal")
            goal_ids.append((username, goal_id, float(target), unit))
            execute(
                """
                INSERT INTO goals (goal_id, user_id, skill_id, title, target_value,
                                   current_value, unit, deadline, status, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'ACTIVE', ?)
                """,
                (
                    goal_id, user_ids[username], skill_ids[(username, skill_name)],
                    title, target, unit,
                    (date.today() + timedelta(days=60)).isoformat(), iso(40),
                ),
            )
            for value in milestones:
                execute(
                    """
                    INSERT INTO milestones (milestone_id, goal_id, title,
                                            target_value, achieved, achieved_at)
                    VALUES (?, ?, ?, ?, 0, NULL)
                    """,
                    (new_id("milestone"), goal_id, f"{value} {unit} reached", float(value)),
                )
                milestone_count += 1

        print(f"✅ Created {len(GOALS)} goals and {milestone_count} milestones")

        # ---- Practice sessions (this also drives goal progress) ------
        session_count = 0
        for username, goal_id, target, unit in goal_ids:
            # Progress roughly 30–70% of the way toward each goal
            fraction = random.uniform(0.3, 0.7)
            goal_row = query_one("SELECT skill_id FROM goals WHERE goal_id = ?", (goal_id,))
            skill_id = goal_row["skill_id"]
            skill_name = query_one(
                "SELECT skill_name FROM skills WHERE skill_id = ?", (skill_id,)
            )["skill_name"]

            if unit == "hours":
                total_minutes = int(target * fraction * 60)
            elif unit == "minutes":
                total_minutes = int(target * fraction)
            else:  # sessions
                total_minutes = int(target * fraction) * 45

            remaining = total_minutes
            day_offset = 1
            while remaining > 0 and day_offset <= 45:
                duration = min(remaining, random.choice([30, 45, 60, 90, 120]))
                execute(
                    """
                    INSERT INTO practice_sessions (session_id, user_id, skill_id,
                                                   duration_minutes, activity, notes,
                                                   practiced_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("session"), user_ids[username], skill_id, duration,
                        random.choice(ACTIVITIES[skill_name]),
                        "Felt good. Focused on fundamentals.",
                        iso(day_offset), iso(day_offset),
                    ),
                )
                remaining -= duration
                day_offset += random.choice([1, 1, 1, 2])   # natural gaps
                session_count += 1

        print(f"✅ Created {session_count} practice sessions")

        # Recalculate goal progress from the sessions we just inserted
        for _, goal_id, _, unit in goal_ids:
            total = query_one(
                """
                SELECT COALESCE(SUM(p.duration_minutes), 0) AS minutes
                FROM practice_sessions p
                JOIN goals g ON g.skill_id = p.skill_id AND g.user_id = p.user_id
                WHERE g.goal_id = ?
                """,
                (goal_id,),
            )["minutes"]

            if unit == "hours":
                value = round(total / 60.0, 2)
            elif unit == "minutes":
                value = float(total)
            else:
                value = float(
                    query_one(
                        """
                        SELECT COUNT(*) AS c
                        FROM practice_sessions p
                        JOIN goals g ON g.skill_id = p.skill_id AND g.user_id = p.user_id
                        WHERE g.goal_id = ?
                        """,
                        (goal_id,),
                    )["c"]
                )

            target_row = query_one("SELECT target_value FROM goals WHERE goal_id = ?", (goal_id,))
            status = "COMPLETED" if value >= float(target_row["target_value"]) else "ACTIVE"
            execute(
                "UPDATE goals SET current_value = ?, status = ? WHERE goal_id = ?",
                (value, status, goal_id),
            )

            # Mark milestones reached
            execute(
                """
                UPDATE milestones
                SET achieved = 1, achieved_at = ?
                WHERE goal_id = ? AND target_value <= ? AND achieved = 0
                """,
                (now_iso(), goal_id, value),
            )

        print("✅ Recalculated goal progress and achieved milestones")

        # ---- Posts --------------------------------------------------
        post_ids: list[str] = []
        for index, (username, skill_name, content) in enumerate(POSTS):
            post_id = new_id("post")
            post_ids.append(post_id)
            execute(
                """
                INSERT INTO posts (post_id, user_id, skill_id, content, media_url, created_at)
                VALUES (?, ?, ?, ?, NULL, ?)
                """,
                (
                    post_id, user_ids[username],
                    skill_ids.get((username, skill_name)),
                    content, iso(index),
                ),
            )
        print(f"✅ Created {len(POSTS)} community posts")

        # ---- Likes --------------------------------------------------
        like_count = 0
        for post_id in post_ids:
            for username in random.sample(list(user_ids.keys()), k=random.randint(1, 3)):
                execute(
                    """
                    INSERT OR IGNORE INTO likes (like_id, post_id, user_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (new_id("like"), post_id, user_ids[username], iso(random.randint(0, 5))),
                )
                like_count += 1
        print(f"✅ Created {like_count} likes")

        # ---- Comments -----------------------------------------------
        comment_count = 0
        for post_id in post_ids:
            for _ in range(random.randint(0, 2)):
                username = random.choice(list(user_ids.keys()))
                execute(
                    """
                    INSERT INTO comments (comment_id, post_id, user_id, content, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("comment"), post_id, user_ids[username],
                        random.choice(COMMENTS), iso(random.randint(0, 5)),
                    ),
                )
                comment_count += 1
        print(f"✅ Created {comment_count} comments")

        # ---- Follows ------------------------------------------------
        follow_pairs = [("bob", "alice"), ("carol", "alice"), ("alice", "carol")]
        for follower, following in follow_pairs:
            execute(
                """
                INSERT OR IGNORE INTO follows (follow_id, follower_id, following_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (new_id("follow"), user_ids[follower], user_ids[following], iso(20)),
            )
        print(f"✅ Created {len(follow_pairs)} follow relationships")

        print("\n" + "=" * 60)
        print("  🌱 Seed complete!")
        print("=" * 60)
        print("  Demo accounts (all use the same password):")
        for spec in USERS:
            print(f"    • {spec['email']:24} / {DEMO_PASSWORD}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    seed()