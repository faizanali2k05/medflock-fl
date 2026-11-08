"""Environment configuration is validated before a worker or public listener starts."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    dataset: Path
    artifacts: Path
    environment: str
    embedded_worker: bool
    auth_required: bool
    api_key: str
    allowed_hosts: list[str]
    issuer: str
    audience: str

    @classmethod
    def load(cls):
        load_dotenv(override=False)
        environment = os.getenv("MEDFLOCK_ENV", "development")
        required = os.getenv("MEDFLOCK_AUTH_REQUIRED", "false").lower() == "true"
        embedded = os.getenv("MEDFLOCK_EMBEDDED_WORKER", "true").lower() == "true"
        key = os.getenv("MEDFLOCK_API_KEY", "")
        issuer = os.getenv("MEDFLOCK_OIDC_ISSUER", "")
        hosts = os.getenv("MEDFLOCK_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
        if environment == "production":
            if not required or embedded or "*" in hosts:
                raise ValueError(
                    "Production requires authentication, explicit hosts and external worker"
                )
            if not issuer and len(key) < 32:
                raise ValueError("Configure OIDC or a strong operator API key")
        return cls(
            os.getenv("MEDFLOCK_DATABASE_URL", "sqlite:///runtime/medflock.db"),
            Path(os.getenv("MEDFLOCK_DATASET", "data/heart_failure.csv")),
            Path(os.getenv("MEDFLOCK_ARTIFACTS", "artifacts")),
            environment,
            embedded,
            required,
            key,
            hosts,
            issuer,
            os.getenv("MEDFLOCK_OIDC_AUDIENCE", "medflock"),
        )
