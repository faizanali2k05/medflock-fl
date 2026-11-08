"""Generate private local configuration without overwriting existing credentials."""

import secrets
from pathlib import Path

path = Path(".env")
if path.exists():
    print("Existing .env preserved")
else:
    path.write_text(
        "MEDFLOCK_ENV=development\n"
        "MEDFLOCK_DATABASE_URL=sqlite:///runtime/medflock.db\n"
        "MEDFLOCK_DATASET=data/heart_failure.csv\n"
        "MEDFLOCK_ARTIFACTS=artifacts\n"
        "MEDFLOCK_PORT=8088\n"
        "MEDFLOCK_EMBEDDED_WORKER=true\n"
        "MEDFLOCK_AUTH_REQUIRED=false\n"
        "MEDFLOCK_ALLOWED_HOSTS=localhost,127.0.0.1,testserver\n"
        f"MEDFLOCK_API_KEY={secrets.token_urlsafe(40)}\n"
        f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n",
        encoding="utf-8",
    )
    print("Created private .env; credentials were not printed")
