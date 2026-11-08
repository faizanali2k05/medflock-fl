"""Registry policy controls eligibility; it never stops a remote hospital process."""

from datetime import datetime, timezone


def effective_status(node, at=None):
    status = node["status"]
    until = node.get("details", {}).get("suspended_until")
    if status == "suspended" and until:
        expiry = datetime.fromisoformat(until)
        if expiry <= (at or datetime.now(timezone.utc)):
            return node["details"].get("resume_status", "paused")
    return status


def training_allowed(node):
    return node is None or effective_status(node) == "active"
