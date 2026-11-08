"""Local accounts use hashed passwords, revocable sessions and explicit role boundaries."""

import hashlib
import hmac
import os
import secrets
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Column, Float, Integer, String, Table, delete, select

from medflock.store import event, metadata

users = Table(
    "accounts",
    metadata,
    Column("id", String, primary_key=True),
    Column("username", String, unique=True, nullable=False),
    Column("password_hash", String, nullable=False),
    Column("role", String, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("node_id", String),
    Column("created_at", Float),
)
sessions = Table(
    "login_sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, nullable=False),
    Column("csrf", String, nullable=False),
    Column("created_at", Float),
    Column("last_seen", Float),
    Column("expires_at", Float),
)
buckets = Table(
    "request_buckets",
    metadata,
    Column("id", String, primary_key=True),
    Column("count", Integer, nullable=False),
    Column("expires_at", Float),
)
router = APIRouter(prefix="/api/auth", tags=["Accounts"])


def password_hash(password):
    salt = secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ":" + value.hex()


def verify_password(password, encoded):
    salt, expected = encoded.split(":")
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return hmac.compare_digest(value.hex(), expected)


DUMMY = password_hash("nonexistent-account-timing-placeholder")


def quota(store, key, limit, seconds=60):
    current = time.time()
    identifier = hashlib.sha256(f"{key}:{int(current // seconds)}".encode()).hexdigest()
    with store.engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        statement = insert(buckets).values(id=identifier, count=1, expires_at=current + seconds * 2)
        count = conn.execute(
            statement.on_conflict_do_update(
                index_elements=["id"], set_={"count": buckets.c.count + 1}
            ).returning(buckets.c.count)
        ).scalar_one()
        conn.execute(delete(buckets).where(buckets.c.expires_at < current))
    if count > limit:
        raise HTTPException(
            429, "Usage limit reached; retry later", headers={"Retry-After": str(seconds)}
        )


def public_user(row):
    return {key: row[key] for key in ["id", "username", "role", "enabled", "node_id"]}


def create_user(store, username, password, role, node_id=None):
    username = username.strip()
    record = dict(
        id=secrets.token_hex(16),
        username=username,
        password_hash=password_hash(password),
        role=role,
        enabled=True,
        node_id=node_id,
        created_at=time.time(),
    )
    with store.engine.begin() as conn:
        if conn.execute(select(users.c.id).where(users.c.username == username)).first():
            raise HTTPException(409, "Username already exists")
        conn.execute(users.insert().values(**record))
    return public_user(record)


def session_principal(request):
    from medflock.security import Principal

    token = request.cookies.get("medflock_session")
    if not token or len(token) > 128:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    current = time.time()
    with request.app.state.store.engine.begin() as conn:
        session = conn.execute(select(sessions).where(sessions.c.id == digest)).mappings().first()
        if not session or session["expires_at"] < current or session["last_seen"] < current - 1800:
            raise HTTPException(401, "Session expired")
        user = (
            conn.execute(select(users).where(users.c.id == session["user_id"])).mappings().first()
        )
        if not user or not user["enabled"]:
            raise HTTPException(401, "Account disabled")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not hmac.compare_digest(
            request.headers.get("x-csrf-token", ""), session["csrf"]
        ):
            raise HTTPException(403, "Valid CSRF token required")
        if session["last_seen"] < current - 60:
            conn.execute(sessions.update().where(sessions.c.id == digest).values(last_seen=current))
    request.state.account = public_user(user)
    request.state.csrf = session["csrf"]
    request.state.session_id = digest
    return Principal(user["id"], frozenset({user["role"]}))


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class NewUser(Login):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{3,64}$")
    password: str = Field(min_length=12, max_length=128)
    role: Literal["admin", "clinician", "researcher", "client", "viewer"]
    node_id: str | None = Field(default=None, max_length=64)


@router.post("/login")
def login(body: Login, request: Request, response: Response):
    store = request.app.state.store
    quota(store, "login-user:" + body.username.lower(), 5, 300)
    with store.engine.connect() as conn:
        row = (
            conn.execute(select(users).where(users.c.username == body.username)).mappings().first()
        )
    valid = verify_password(body.password, row["password_hash"] if row else DUMMY)
    if not row or not valid or not row["enabled"]:
        raise HTTPException(401, "Invalid username or password")
    token, csrf, current = secrets.token_urlsafe(32), secrets.token_urlsafe(32), time.time()
    with store.engine.begin() as conn:
        conn.execute(delete(sessions).where(sessions.c.expires_at < current))
        active = (
            conn.execute(
                select(sessions)
                .where(sessions.c.user_id == row["id"])
                .order_by(sessions.c.created_at.desc())
            )
            .mappings()
            .all()
        )
        for old in active[4:]:
            conn.execute(delete(sessions).where(sessions.c.id == old["id"]))
        conn.execute(
            sessions.insert().values(
                id=hashlib.sha256(token.encode()).hexdigest(),
                user_id=row["id"],
                csrf=csrf,
                created_at=current,
                last_seen=current,
                expires_at=current + 28800,
            )
        )
        event(conn, "account.login", {"actor": row["id"]})
    response.set_cookie(
        "medflock_session",
        token,
        httponly=True,
        secure=os.getenv("MEDFLOCK_COOKIE_SECURE", "true") == "true",
        samesite="strict",
        max_age=28800,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"user": public_user(row), "csrf": csrf}


@router.get("/me")
def me(request: Request):
    principal = session_principal(request)
    if not principal:
        raise HTTPException(401, "Login required")
    return {"user": request.state.account, "csrf": request.state.csrf}


@router.post("/logout")
def logout(request: Request, response: Response):
    if not session_principal(request):
        raise HTTPException(401, "Login required")
    with request.app.state.store.engine.begin() as conn:
        conn.execute(delete(sessions).where(sessions.c.id == request.state.session_id))
    response.delete_cookie("medflock_session", path="/")
    return {"logged_out": True}


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


@router.post("/password")
def change_password(body: PasswordChange, request: Request, response: Response):
    principal = session_principal(request)
    if not principal:
        raise HTTPException(401, "Login required")
    store = request.app.state.store
    quota(store, "password:" + principal.subject, 5, 300)
    with store.engine.begin() as conn:
        row = conn.execute(select(users).where(users.c.id == principal.subject)).mappings().one()
        if not verify_password(body.current_password, row["password_hash"]):
            raise HTTPException(401, "Current password incorrect")
        conn.execute(
            users.update()
            .where(users.c.id == principal.subject)
            .values(password_hash=password_hash(body.new_password))
        )
        conn.execute(delete(sessions).where(sessions.c.user_id == principal.subject))
        event(conn, "account.password_changed", {"actor": principal.subject})
    response.delete_cookie("medflock_session", path="/")
    return {"login_required": True}
