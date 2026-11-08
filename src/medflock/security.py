"""Operator keys and OIDC tokens share explicit permissions without exposing secrets to the UI."""

import hmac
from dataclasses import dataclass

import jwt
from fastapi import HTTPException
from starlette.requests import HTTPConnection


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]

    def require(self, role="read"):
        if role == "clinician":
            allowed = "clinician" in self.roles
        elif role == "client":
            allowed = bool(self.roles & {"client", "hospital", "admin", "operator"})
        elif role == "admin":
            allowed = "admin" in self.roles
        elif "admin" in self.roles or "operator" in self.roles:
            allowed = True
        elif role == "read":
            allowed = bool(self.roles & {"researcher", "viewer", "clinician", "hospital"})
        else:
            allowed = role in self.roles
        if not allowed:
            raise HTTPException(403, f"The {role} role is required")


def authenticate(connection: HTTPConnection):
    if getattr(connection.state, "principal", None):
        return connection.state.principal
    from medflock.accounts import session_principal

    principal = session_principal(connection)
    if principal:
        return principal
    settings = connection.app.state.settings
    if not settings.auth_required:
        return Principal("local-developer", frozenset({"operator"}))
    header = connection.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "Bearer authentication required")
    token = header[7:]
    if settings.api_key and hmac.compare_digest(token, settings.api_key):
        return Principal("operator-key", frozenset({"operator"}))
    if settings.issuer:
        try:
            key = connection.app.state.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=settings.issuer,
                audience=settings.audience,
                options={"require": ["exp", "sub"]},
            )
            roles = set(claims.get("realm_access", {}).get("roles", []))
            principal = Principal(
                claims["sub"], frozenset(roles & {"researcher", "operator", "clinician", "viewer"})
            )
            principal.require()
            return principal
        except jwt.PyJWTError:
            pass
    raise HTTPException(401, "Invalid or expired credentials")
