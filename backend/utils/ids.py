"""
ID generation.

We use prefixed UUID4 hex strings instead of auto-increment integers so
that IDs are (a) globally unique across shards and (b) not enumerable by
an attacker who could otherwise guess /api/posts/1, /api/posts/2, ...
"""
from uuid import uuid4

PREFIXES = {
    "user": "usr",
    "skill": "skl",
    "goal": "gol",
    "milestone": "mst",
    "session": "ses",
    "post": "pst",
    "comment": "cmt",
    "like": "lke",
    "follow": "flw",
    "file": "fil",
}


def new_id(kind: str) -> str:
    """Generate a new prefixed identifier, e.g. new_id('user') -> 'usr_3f9a...'."""
    prefix = PREFIXES.get(kind, "obj")
    return f"{prefix}_{uuid4().hex}"