"""
backend/app/core/security.py
============================
Production-grade security utilities for the AI Powered Career Learning Platform.

This module is intentionally a **pure utility layer** — it contains no business
logic, no database access, and no FastAPI routing concerns.  It is the single
source of truth for every cryptographic operation performed by the backend.

──────────────────────────────────────────────────────────────────────────────
PASSWORD HASHING — WHY bcrypt?
──────────────────────────────────────────────────────────────────────────────
bcrypt is a deliberately slow, adaptive hashing algorithm designed by Niels
Provos and David Mazières (1999).  Its key properties for production use are:

  • Work factor (cost):  The number of internal rounds is configurable via a
    "cost" parameter (default 12 in Passlib).  This means hashing remains
    computationally expensive even as hardware improves — simply raise the cost
    factor in future deployments.

  • Salt embedded:  bcrypt automatically generates and embeds a 128-bit random
    salt in the output hash, preventing pre-computed rainbow-table attacks.

  • Timing-safe comparison:  Passlib's verify() performs a constant-time
    comparison, eliminating timing side-channel leaks.

  • OWASP recommendation:  bcrypt (with cost ≥ 12) is on OWASP's approved list
    for password storage (OWASP ASVS v4.0, section 2.4.1).

Alternatives considered:
  • Argon2id — better memory hardness, preferred for new systems; use
    passlib[argon2] if upgrading in the future.
  • scrypt — good choice but less ecosystem support.
  • PBKDF2 — compliant with FIPS 140-2, but less resistant to GPU attacks.

──────────────────────────────────────────────────────────────────────────────
JSON WEB TOKENS (JWT)
──────────────────────────────────────────────────────────────────────────────
JWTs (RFC 7519) are self-contained, signed tokens that encode claims as a
Base64URL-encoded JSON payload.  The backend issues **two** token types:

  Access Token:
    • Short-lived (default 30 minutes, see ACCESS_TOKEN_EXPIRE_MINUTES).
    • Sent by the client on every authenticated HTTP request via
      `Authorization: Bearer <token>`.
    • Stateless — the server validates the signature and expiry without a
      database round-trip, enabling horizontal scaling.
    • Payload claim `type="access"` allows the server to reject a refresh
      token being used where an access token is expected.

  Refresh Token:
    • Long-lived (default 7 days, see REFRESH_TOKEN_EXPIRE_DAYS).
    • Used solely to obtain a new access token without re-authentication.
    • Should be stored securely on the client (HttpOnly cookie recommended).
    • Payload claim `type="refresh"` prevents misuse as an access token.
    • In a full implementation, refresh tokens should be stored server-side
      (Redis / DB) and invalidated on logout or suspicious activity (token
      rotation).

Standard claims used:
  • sub  (subject)   — the entity the token represents (e.g., user UUID).
  • exp  (expiry)    — UTC Unix timestamp after which the token is invalid.
  • iat  (issued at) — UTC Unix timestamp when the token was minted.
  • type             — custom claim to differentiate access vs. refresh tokens.

Algorithm:
  • HS256 (HMAC-SHA256) — symmetric signing using the application's
    SECRET_KEY.  All services sharing the key can verify tokens.
  • For multi-service architectures consider RS256 (asymmetric) so that
    resource servers can verify without holding the signing key.

Security best practices implemented here:
  • Timezone-aware datetimes with `timezone.utc` to avoid naive-datetime bugs.
  • Explicit `exp` validation via `options={"verify_exp": True}` (python-jose
    default).
  • `algorithms` parameter is always passed as a list to prevent the "alg:none"
    downgrade attack.
  • No sensitive data (passwords, PII) is placed in the JWT payload — JWTs
    are signed, NOT encrypted; anyone can base64-decode the payload.

──────────────────────────────────────────────────────────────────────────────
USAGE EXAMPLE
──────────────────────────────────────────────────────────────────────────────
    from app.core.security import (
        get_password_hash,
        verify_password,
        create_access_token,
        create_refresh_token,
        decode_token,
    )

    # Registration
    hashed = get_password_hash("super-secret-password")

    # Login
    if verify_password("super-secret-password", hashed):
        access_token  = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))

    # Protected route — token validation
    payload = decode_token(access_token)   # raises JWTError if invalid
    user_id = payload["sub"]
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt  # noqa: F401  (JWTError re-exported for callers)
from passlib.context import CryptContext

from app.core.config import settings

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

__all__: list[str] = [
    "password_context",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
]

# ─────────────────────────────────────────────────────────────────────────────
# Internal constants
# ─────────────────────────────────────────────────────────────────────────────

# Token type discriminators — stored in the JWT payload's `type` claim.
# Using typed constants (rather than raw strings) avoids subtle typo bugs and
# enables IDE rename-refactoring across the entire codebase.
_ACCESS_TOKEN_TYPE: str = "access"
_REFRESH_TOKEN_TYPE: str = "refresh"

# ─────────────────────────────────────────────────────────────────────────────
# Password hashing — singleton CryptContext
# ─────────────────────────────────────────────────────────────────────────────

# Why a module-level singleton?
#
#   CryptContext initialisation is non-trivial: Passlib loads algorithm
#   implementations, validates the configuration, and sets up internal state.
#   Constructing it once at import time (rather than on every function call)
#   eliminates repeated overhead on hot authentication paths.
#
#   `schemes=["bcrypt"]`   — bcrypt is the only accepted hashing algorithm.
#   `deprecated="auto"`    — any hash produced with an older/weaker scheme is
#                            automatically flagged for rehashing on next login,
#                            enabling zero-downtime algorithm migration in the
#                            future (e.g., transitioning to Argon2id).
password_context: CryptContext = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


# ─────────────────────────────────────────────────────────────────────────────
# Password utilities
# ─────────────────────────────────────────────────────────────────────────────


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash.

    Passlib's :py:meth:`CryptContext.verify` performs a **constant-time**
    comparison, which means the function takes the same amount of time
    regardless of whether the password matches or not.  This prevents
    timing-based side-channel attacks that could reveal information about
    the stored hash.

    Parameters
    ----------
    plain_password:
        The raw password supplied by the user (e.g. from a login form).
    hashed_password:
        The bcrypt hash retrieved from the database for the given user.

    Returns
    -------
    bool
        ``True`` if the password matches the hash, ``False`` otherwise.

    Notes
    -----
    Never compare password hashes using ``==`` or ``hmac.compare_digest``
    directly — always delegate to Passlib, which handles algorithm-specific
    nuances (encoding, salt extraction, cost factor).

    Example
    -------
    ::

        if not verify_password(form.password, db_user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    """
    return password_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plain-text password using bcrypt.

    Passlib automatically:
      - Generates a cryptographically random 128-bit salt.
      - Applies the configured bcrypt cost factor (default: 12 rounds).
      - Encodes the algorithm identifier, cost, salt, and digest into a
        single portable string (Modular Crypt Format / PHC string format).

    Parameters
    ----------
    password:
        The raw password to hash.  Should already have been validated for
        minimum length / complexity by the Pydantic schema layer before
        reaching this function.

    Returns
    -------
    str
        A 60-character bcrypt hash string safe to store in the database.

    Security note
    -------------
    bcrypt silently truncates input at 72 bytes.  If your password policy
    allows very long passphrases, consider pre-hashing with SHA-256 before
    passing to bcrypt (the "shucking" mitigation).  For this platform's
    current requirements the 72-byte limit is acceptable.

    Example
    -------
    ::

        user.hashed_password = get_password_hash(schema.password)
        db.add(user)
    """
    return password_context.hash(password)


# ─────────────────────────────────────────────────────────────────────────────
# JWT utilities — internal helper
# ─────────────────────────────────────────────────────────────────────────────


def _build_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    """Construct and sign a JWT with the standard claim set.

    This private factory is shared by :func:`create_access_token` and
    :func:`create_refresh_token` to eliminate duplication while keeping the
    public API surface minimal and explicit.

    Parameters
    ----------
    subject:
        The ``sub`` claim value — typically the user's UUID as a string.
    token_type:
        Value for the custom ``type`` claim (``"access"`` or ``"refresh"``).
    expires_delta:
        How long from *now* the token should remain valid.

    Returns
    -------
    str
        A compact, URL-safe, period-delimited JWT string
        (``header.payload.signature``).
    """
    now: datetime = datetime.now(tz=timezone.utc)
    expire: datetime = now + expires_delta

    payload: dict[str, Any] = {
        # ── RFC 7519 registered claims ────────────────────────────────────── #
        "sub": subject,   # Subject   — who the token represents
        "exp": expire,    # Expiry    — python-jose accepts a datetime object
        "iat": now,       # Issued-at — useful for token age / reuse detection
        # ── Custom discriminator claim ────────────────────────────────────── #
        # Prevents cross-type token misuse: a refresh token is rejected when
        # the caller expects an access token, and vice versa, even if both are
        # cryptographically valid for the same SECRET_KEY.
        "type": token_type,
    }

    # `algorithm` is always passed explicitly (not read from the token header)
    # to prevent the well-known "alg:none" vulnerability, where an attacker
    # crafts a token with no signature and sets alg to "none".
    encoded_jwt: str = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


# ─────────────────────────────────────────────────────────────────────────────
# JWT utilities — public API
# ─────────────────────────────────────────────────────────────────────────────


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a short-lived JWT access token.

    Access tokens are the primary authentication credential sent by the client
    on every protected API request via the ``Authorization: Bearer`` header.
    They are **stateless** — the server validates the cryptographic signature
    and expiry time without consulting the database, allowing the API to scale
    horizontally without a shared session store.

    Parameters
    ----------
    subject:
        A string that uniquely identifies the principal (typically
        ``str(user.id)`` or the user's email).  Stored in the ``sub`` claim.
    expires_delta:
        Override the default TTL defined by
        :attr:`~app.core.config.Settings.ACCESS_TOKEN_EXPIRE_MINUTES`.
        Pass an explicit :class:`~datetime.timedelta` when you need a
        non-standard lifetime (e.g., a short-lived one-time email-verification
        token).

    Returns
    -------
    str
        A signed, compact JWT string.

    Payload claims
    --------------
    =========  =================================================
    ``sub``    Subject — the ``subject`` parameter value.
    ``exp``    Expiry  — UTC timestamp (now + TTL).
    ``iat``    Issued-at — current UTC timestamp.
    ``type``   ``"access"`` — discriminator claim.
    =========  =================================================

    Example
    -------
    ::

        token = create_access_token(subject=str(user.id))
        return {"access_token": token, "token_type": "bearer"}
    """
    delta: timedelta = expires_delta or timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return _build_token(
        subject=subject,
        token_type=_ACCESS_TOKEN_TYPE,
        expires_delta=delta,
    )


def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a long-lived JWT refresh token.

    Refresh tokens are used **solely** to obtain a new access token once the
    current one expires, without requiring the user to re-enter credentials.
    They should be stored securely on the client side — preferably in an
    ``HttpOnly``, ``Secure``, ``SameSite=Strict`` cookie to prevent JavaScript
    access and CSRF-based token theft.

    Design considerations
    ---------------------
    • The ``type="refresh"`` claim allows the token validation layer to
      reject a refresh token when an access token is expected, and vice versa.
    • In a production deployment, refresh tokens should be persisted in a
      server-side store (Redis or database) so they can be **rotated** and
      **revoked** (e.g., on logout, suspicious IP change, or detected reuse).
      This module intentionally omits that persistence — it belongs in the
      service / repository layers.

    Parameters
    ----------
    subject:
        A string uniquely identifying the principal (typically ``str(user.id)``).
    expires_delta:
        Override the default TTL defined by
        :attr:`~app.core.config.Settings.REFRESH_TOKEN_EXPIRE_DAYS`.

    Returns
    -------
    str
        A signed, compact JWT string.

    Payload claims
    --------------
    =========  =================================================
    ``sub``    Subject — the ``subject`` parameter value.
    ``exp``    Expiry  — UTC timestamp (now + TTL).
    ``iat``    Issued-at — current UTC timestamp.
    ``type``   ``"refresh"`` — discriminator claim.
    =========  =================================================

    Example
    -------
    ::

        refresh_token = create_refresh_token(subject=str(user.id))
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
        )
    """
    delta: timedelta = expires_delta or timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return _build_token(
        subject=subject,
        token_type=_REFRESH_TOKEN_TYPE,
        expires_delta=delta,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, returning its payload as a plain dictionary.

    This function delegates all cryptographic validation to ``python-jose``,
    which performs the following checks automatically:

      1. **Signature verification** — the token's HMAC-SHA256 signature is
         recomputed using :attr:`~app.core.config.Settings.SECRET_KEY` and
         compared against the embedded signature.  A mismatch raises
         :class:`~jose.JWTError`.
      2. **Expiry check** — if ``exp`` is in the past,
         :class:`~jose.ExpiredSignatureError` (a subclass of
         :class:`~jose.JWTError`) is raised automatically.
      3. **Algorithm enforcement** — only the algorithm declared in
         :attr:`~app.core.config.Settings.ALGORITHM` is accepted, preventing
         algorithm-confusion / "alg:none" downgrade attacks.

    This function deliberately does **not** inspect the ``type`` claim — that
    responsibility belongs to the caller (e.g., the authentication dependency
    or the refresh-token endpoint), which knows whether it expects an access or
    a refresh token.

    Parameters
    ----------
    token:
        The raw JWT string received from the client (stripped of any
        ``Bearer `` prefix before calling this function).

    Returns
    -------
    dict[str, Any]
        The decoded payload dictionary.  Typical keys: ``sub``, ``exp``,
        ``iat``, ``type``.

    Raises
    ------
    jose.JWTError
        Raised for any of the following conditions:

        * Invalid or tampered signature.
        * Token has expired (``ExpiredSignatureError``).
        * Malformed token structure (wrong number of segments, bad Base64).
        * Algorithm mismatch.

    Example
    -------
    ::

        from jose import JWTError
        from fastapi import status

        try:
            payload = decode_token(token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token type",
            )

        user_id: str = payload["sub"]
    """
    # Delegating to python-jose; any cryptographic failure surfaces as a
    # JWTError subclass (ExpiredSignatureError, JWTClaimsError, etc.).
    # Re-raised as-is so callers can catch `JWTError` uniformly without
    # needing to import jose directly.
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    return payload
