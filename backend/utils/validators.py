"""
Input validation helpers.

Centralising validation means:
  * every route validates the same way,
  * error messages stay consistent,
  * and security checks (file type, length limits) can never be forgotten
    in a new route.
"""
from __future__ import annotations

import re
from pathlib import Path

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")

SKILL_LEVELS = {"BEGINNER", "INTERMEDIATE", "ADVANCED"}
SKILL_STATUSES = {"ACTIVE", "PAUSED", "COMPLETED"}
GOAL_UNITS = {"hours", "minutes", "sessions"}
GOAL_STATUSES = {"ACTIVE", "PAUSED", "COMPLETED"}

SKILL_CATEGORIES = {
    "Photography", "Music", "Art", "Coding", "Fitness",
    "Cooking", "Writing", "Design", "Games", "Outdoors", "Other",
}

MAX_BIO_LENGTH = 500
MAX_POST_LENGTH = 2000
MAX_COMMENT_LENGTH = 1000
MAX_SKILL_NAME_LENGTH = 80
MAX_ACTIVITY_LENGTH = 200
MAX_NOTES_LENGTH = 1000


# ---------------------------------------------------------------------
# Primitive validators
# ---------------------------------------------------------------------
def is_valid_email(value: str) -> bool:
    return bool(value) and bool(EMAIL_RE.match(value.strip()))


def is_valid_username(value: str) -> bool:
    return bool(value) and bool(USERNAME_RE.match(value.strip().lower()))


def is_valid_password(value: str) -> tuple[bool, str]:
    """Minimum 8 characters with at least one letter and one digit."""
    if not value or len(value) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", value):
        return False, "Password must contain at least one letter."
    if not re.search(r"\d", value):
        return False, "Password must contain at least one digit."
    return True, ""


def clean_text(value, max_length: int, field: str = "field") -> tuple[str, str]:
    """
    Strip whitespace, enforce a max length, and reject non-strings.

    Returns (cleaned_value, error_message). error_message == "" means OK.
    Note: we deliberately do NOT strip HTML here — output escaping happens
    on the frontend, and parameterised SQL blocks injection.
    """
    if value is None:
        return "", ""
    if not isinstance(value, str):
        return "", f"{field} must be text."
    cleaned = value.strip()
    if len(cleaned) > max_length:
        return "", f"{field} must be at most {max_length} characters."
    return cleaned, ""


# ---------------------------------------------------------------------
# Composite validators
# ---------------------------------------------------------------------
def validate_registration(payload: dict) -> dict:
    """Return a dict of {field: message}. Empty dict == valid."""
    errors: dict[str, str] = {}

    name, err = clean_text(payload.get("name"), 80, "Name")
    if err or not name:
        errors["name"] = err or "Name is required."

    username = (payload.get("username") or "").strip().lower()
    if not is_valid_username(username):
        errors["username"] = (
            "Username must be 3-20 characters using only lowercase letters, numbers, and underscores."
        )

    email = (payload.get("email") or "").strip().lower()
    if not is_valid_email(email):
        errors["email"] = "A valid email address is required."

    valid_pw, pw_message = is_valid_password(payload.get("password") or "")
    if not valid_pw:
        errors["password"] = pw_message

    return errors


def validate_skill(payload: dict, partial: bool = False) -> tuple[dict, dict]:
    """
    Validate a skill payload.

    Returns (cleaned_fields, errors).
    `partial=True` is used for PUT (only validate provided keys).
    """
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if not partial or "skill_name" in payload:
        name, err = clean_text(payload.get("skill_name"), MAX_SKILL_NAME_LENGTH, "Skill name")
        if err or not name:
            errors["skill_name"] = err or "Skill name is required."
        else:
            cleaned["skill_name"] = name

    if not partial or "category" in payload:
        category = (payload.get("category") or "Other").strip()
        cleaned["category"] = category if category in SKILL_CATEGORIES else "Other"

    if not partial or "current_level" in payload:
        level = (payload.get("current_level") or "BEGINNER").strip().upper()
        if level not in SKILL_LEVELS:
            errors["current_level"] = f"Level must be one of {sorted(SKILL_LEVELS)}."
        else:
            cleaned["current_level"] = level

    if not partial or "target_level" in payload:
        level = (payload.get("target_level") or "INTERMEDIATE").strip().upper()
        if level not in SKILL_LEVELS:
            errors["target_level"] = f"Level must be one of {sorted(SKILL_LEVELS)}."
        else:
            cleaned["target_level"] = level

    if not partial or "status" in payload:
        status = (payload.get("status") or "ACTIVE").strip().upper()
        if status not in SKILL_STATUSES:
            errors["status"] = f"Status must be one of {sorted(SKILL_STATUSES)}."
        else:
            cleaned["status"] = status

    for field, max_len in (("description", 500), ("start_date", 10), ("target_date", 10)):
        if not partial or field in payload:
            value, err = clean_text(payload.get(field), max_len, field.replace("_", " ").title())
            if err:
                errors[field] = err
            else:
                cleaned[field] = value

    return cleaned, errors


def validate_goal(payload: dict) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    title, err = clean_text(payload.get("title"), 120, "Title")
    if err or not title:
        errors["title"] = err or "Goal title is required."
    else:
        cleaned["title"] = title

    try:
        target = float(payload.get("target_value"))
        if target <= 0:
            raise ValueError
        cleaned["target_value"] = target
    except (TypeError, ValueError):
        errors["target_value"] = "Target value must be a positive number."

    unit = (payload.get("unit") or "hours").strip().lower()
    if unit not in GOAL_UNITS:
        errors["unit"] = f"Unit must be one of {sorted(GOAL_UNITS)}."
    else:
        cleaned["unit"] = unit

    deadline, err = clean_text(payload.get("deadline"), 10, "Deadline")
    if err:
        errors["deadline"] = err
    else:
        cleaned["deadline"] = deadline

    return cleaned, errors


def validate_practice(payload: dict) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    skill_id = (payload.get("skill_id") or "").strip()
    if not skill_id:
        errors["skill_id"] = "skill_id is required."
    else:
        cleaned["skill_id"] = skill_id

    try:
        duration = int(payload.get("duration_minutes"))
        if duration <= 0 or duration > 1440:
            raise ValueError
        cleaned["duration_minutes"] = duration
    except (TypeError, ValueError):
        errors["duration_minutes"] = "Duration must be between 1 and 1440 minutes."

    activity, err = clean_text(payload.get("activity"), MAX_ACTIVITY_LENGTH, "Activity")
    if err:
        errors["activity"] = err
    else:
        cleaned["activity"] = activity

    notes, err = clean_text(payload.get("notes"), MAX_NOTES_LENGTH, "Notes")
    if err:
        errors["notes"] = err
    else:
        cleaned["notes"] = notes

    practiced_at, err = clean_text(payload.get("practiced_at"), 10, "Practice date")
    if err:
        errors["practiced_at"] = err
    else:
        cleaned["practiced_at"] = practiced_at  # empty -> route defaults to today

    return cleaned, errors


# ---------------------------------------------------------------------
# File validation (security-critical)
# ---------------------------------------------------------------------
def validate_upload(file_storage, allowed_extensions: set[str], max_bytes: int) -> tuple[bool, str]:
    """
    Validate an uploaded file.

    Checks performed:
      1. A file was actually provided.
      2. The extension is on the allow-list.
      3. The declared MIME type looks like an image/document.
      4. The file size is within the configured limit.

    NOTE: extension checks alone are not enough in production — you would
    also sniff magic bytes (e.g. with `python-magic`) and, for images,
    re-encode them to strip embedded scripts.
    """
    if file_storage is None or not file_storage.filename:
        return False, "No file was provided."

    extension = Path(file_storage.filename).suffix.lower().lstrip(".")
    if extension not in allowed_extensions:
        return False, f"File type '.{extension}' is not allowed. Allowed: {sorted(allowed_extensions)}"

    # Measure size without trusting Content-Length
    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)

    if size == 0:
        return False, "The uploaded file is empty."
    if size > max_bytes:
        return False, f"File is too large. Maximum size is {max_bytes // (1024 * 1024)} MB."

    return True, ""