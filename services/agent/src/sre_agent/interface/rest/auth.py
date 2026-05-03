"""Azure AD OIDC auth — auth code flow + signed-cookie sessions.

This is a deliberately small implementation:
- We trust Microsoft's `/token` endpoint to validate the authorization code; the
  ID token returned over TLS is decoded without signature verification.
  For production you'd verify against the JWKS at the discovery URL.
- Sessions are HMAC-signed JSON cookies (stdlib only, no extra deps).

Flow:
1. /auth/login           → redirect user to AAD authorize endpoint (state + nonce)
2. AAD redirects to /auth/callback with `code` + `state`
3. /auth/callback exchanges code for ID token, decodes claims, sets session cookie
4. /auth/me              → returns current identity (or null)
5. /auth/logout          → clears cookie
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from sre_agent.common.config import get_settings
from sre_agent.interface.rest.dependencies import get_container

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE = "sre_session"
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60  # 8 hours
STATE_COOKIE = "sre_oauth_state"
STATE_MAX_AGE_SECONDS = 600


@dataclass(frozen=True, slots=True, kw_only=True)
class Identity:
    email: str
    name: str
    oid: str  # AAD object ID
    roles: tuple[str, ...]
    issued_at: int

    def has_role(self, role: str) -> bool:
        return role in self.roles or "admin" in self.roles


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign_session(payload: dict, secret: str) -> str:
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64url_encode(
        hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    )
    return f"{body}.{sig}"


def _verify_session(token: str, secret: str) -> dict | None:
    try:
        body, sig = token.split(".")
        expected = _b64url_encode(
            hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64url_decode(body).decode())
        if not isinstance(payload, dict):
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except (ValueError, json.JSONDecodeError):
        return None


def _decode_id_token(id_token: str) -> dict:
    """Decode JWT body without verifying signature.

    Safe in this flow because the token came directly from Microsoft's `/token`
    endpoint over TLS, in response to a code we just generated.
    """
    parts = id_token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed id_token")
    return json.loads(_b64url_decode(parts[1]).decode())


def _admin_emails() -> set[str]:
    raw = get_settings().auth_admin_emails or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _roles_for(email: str) -> tuple[str, ...]:
    if email.lower() in _admin_emails():
        return ("admin", "responder", "viewer")
    return ("viewer",)


def get_current_identity(
    sre_session: str | None = Cookie(default=None),
) -> Identity | None:
    """FastAPI dependency: returns the current identity, or None if anonymous."""
    if not sre_session:
        return None
    settings = get_settings()
    payload = _verify_session(sre_session, settings.auth_session_secret)
    if payload is None:
        return None
    return Identity(
        email=str(payload.get("email", "")),
        name=str(payload.get("name", "")),
        oid=str(payload.get("oid", "")),
        roles=tuple(payload.get("roles") or ()),
        issued_at=int(payload.get("iat", 0)),
    )


def require_identity(
    identity: Identity | None = Depends(get_current_identity),
) -> Identity:
    """Enforce an authenticated user; raises 401 otherwise."""
    if identity is None:
        if not get_settings().auth_required:
            # In permissive mode, accept anonymous-but-tagged identity.
            return Identity(
                email="anonymous@local", name="anonymous", oid="anon",
                roles=("viewer",), issued_at=int(time.time()),
            )
        raise HTTPException(status_code=401, detail="login required")
    return identity


def require_role(role: str):
    def _dep(identity: Identity = Depends(require_identity)) -> Identity:
        if not identity.has_role(role):
            raise HTTPException(
                status_code=403,
                detail=f"role '{role}' required (you have {list(identity.roles)})",
            )
        return identity
    return _dep


@router.get("/login")
async def login(request: Request, next_url: str | None = None) -> RedirectResponse:
    settings = get_settings()
    if not settings.aad_client_id:
        raise HTTPException(500, "AAD_CLIENT_ID not configured")
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(16)
    state_payload = {
        "state": state,
        "nonce": nonce,
        "next": next_url or settings.aad_post_login_redirect,
        "exp": int(time.time()) + STATE_MAX_AGE_SECONDS,
    }
    signed_state = _sign_session(state_payload, settings.auth_session_secret)
    tenant = settings.aad_tenant_id or "common"
    authorize_url = (
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?"
        + urlencode({
            "client_id": settings.aad_client_id,
            "response_type": "code",
            "redirect_uri": settings.aad_redirect_uri,
            "response_mode": "query",
            "scope": "openid profile email offline_access",
            "state": state,
            "nonce": nonce,
            "prompt": "select_account",
        })
    )
    response = RedirectResponse(url=authorize_url, status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        signed_state,
        max_age=STATE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,  # dev only; flip True behind HTTPS
        path="/",
    )
    return response


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    sre_oauth_state: str | None = Cookie(default=None),
) -> Response:
    settings = get_settings()
    if error:
        return JSONResponse(
            {"error": error, "description": error_description}, status_code=400
        )
    if not code or not state or not sre_oauth_state:
        raise HTTPException(400, "missing code/state")
    state_payload = _verify_session(sre_oauth_state, settings.auth_session_secret)
    if state_payload is None or state_payload.get("state") != state:
        raise HTTPException(400, "invalid or expired state")

    tenant = settings.aad_tenant_id or "common"
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.post(
                token_url,
                data={
                    "client_id": settings.aad_client_id,
                    "client_secret": settings.aad_client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.aad_redirect_uri,
                    "scope": "openid profile email offline_access",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            log.warning("aad token exchange failed", body=exc.response.text)
            raise HTTPException(400, f"token exchange failed: {exc.response.text}") from exc

    body = r.json()
    id_token = body.get("id_token")
    if not id_token:
        raise HTTPException(400, "no id_token in token response")
    claims = _decode_id_token(id_token)
    if claims.get("nonce") != state_payload.get("nonce"):
        raise HTTPException(400, "nonce mismatch")

    email = (
        claims.get("email")
        or claims.get("preferred_username")
        or claims.get("upn")
        or ""
    ).lower()
    name = claims.get("name") or email or "unknown"
    oid = claims.get("oid") or claims.get("sub") or ""
    roles = _roles_for(email)

    session_payload = {
        "email": email,
        "name": name,
        "oid": oid,
        "roles": list(roles),
        "iat": int(time.time()),
        "exp": int(time.time()) + SESSION_MAX_AGE_SECONDS,
    }
    signed = _sign_session(session_payload, settings.auth_session_secret)

    next_url = state_payload.get("next") or settings.aad_post_login_redirect
    response = RedirectResponse(url=next_url, status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        signed,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    response.delete_cookie(STATE_COOKIE, path="/")
    log.info("auth: login success", email=email, roles=list(roles))
    return response


@router.get("/me")
async def me(identity: Identity | None = Depends(get_current_identity)) -> dict:
    if identity is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "email": identity.email,
        "name": identity.name,
        "roles": list(identity.roles),
    }


@router.post("/logout")
async def logout() -> Response:
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response
