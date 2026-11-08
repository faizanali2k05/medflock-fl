"""Bootstrap one administrator from standard input; credentials never become source files."""

import json
import sys

from sqlalchemy import select

from medflock.accounts import NewUser, create_user, users
from medflock.config import Settings
from medflock.store import Store

if __name__ == "__main__":
    body = NewUser.model_validate(json.load(sys.stdin))
    if body.role != "admin":
        raise ValueError("Bootstrap requires an administrator")
    store = Store(Settings.load().database_url)
    with store.engine.connect() as conn:
        exists = conn.execute(select(users.c.id).where(users.c.role == "admin")).first()
    if exists:
        raise ValueError("An administrator already exists; use authenticated account management")
    create_user(store, body.username, body.password, body.role)
    print("Administrator initialized")
