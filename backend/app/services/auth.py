"""
backend/app/services/auth.py
=============================
Authentication business-logic service for the AI Powered Career Learning Platform.

This module is the **orchestration layer** that sits between the HTTP transport
(FastAPI routes) and the data-access layer (``UserRepository``).  It is the
single source of truth for all authentication decisions and workflows.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLEAN ARCHITECTURE BOUNDARIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌────────────────────────────────────────────────────┐
  │  HTTP Layer  (app/api/v1/auth/*.py)                │
  │  - Receives HTTP request, validates input schema   │
  │  - Calls AuthService methods                       │
  │  - Converts ServiceError → HTTPException           │
  ├────────────────────────────────────────────────────┤
  │  AuthService  (this file)                          │
  │  - Business logic: duplicate checks, auth rules   │
  │  - Password hashing via security.py               │
  │  - JWT creation / decoding via security.py        │
  │  - All DB access delegated to UserRepository      │
  │  - Raises AuthError (NOT HTTPException)            │
  ├────────────────────────────────────────────────────┤
  │  UserRepository  (app/repositories/user.py)        │
  │  - SQL queries only                               │
  │  - Returns ORM User objects                       │
  ├────────────────────────────────────────────────────┤
  │  SQLAlchemy Session  /  PostgreSQL                 │
  └────────────────────────────────────────────────────┘

Layer rules enforced here:
  • No ``FastAPI`` imports — no ``HTTPException``, ``Request``, ``Depends``.
  • No raw SQL — every DB access goes through ``UserRepository``.
  • No password handling outside of delegating to ``security.hash_password``
    and ``security.verify_password``.
  • Raises domain-specific ``AuthError`` (defined below) for all business
    rule violations.  The HTTP layer maps those to appropriate HTTP status
    codes without any service-layer coupling.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRANSACTION OWNERSHIP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The ``Session`` is always injected from outside (via FastAPI's ``Depends``
or a test fixture).  ``AuthService`` commits after successful write operations
and never calls ``session.close()``.  If an ``AuthError`` is raised mid-way,
the session remains uncommitted; the caller (route handler) is responsible
for rollback via the ``get_db`` dependency's error path.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
::

    from sqlalchemy.orm import Session
    from app.services.auth import AuthService, AuthError
    from app.schemas import UserCreate

    def register(db: Session, payload: UserCreate):
        svc = AuthService(db)
        try:
            user_resp, tokens = svc.register_user(payload)
        except AuthError as e:
            # Map to HTTPException in the route layer
            raise

    # Or use the thin factory helper:
    svc = AuthService.from_session(db)
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    RefreshTokenRequest,
)
from app.schemas.token import (
    AccessTokenResponse,
    TokenPayload,
    TokenResponse,
)
from app.schemas.user import UserCreate, UserResponse

logger: logging.Logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Domain exception — raised instead of HTTPException
# ─────────────────────────────────────────────────────────────────────────────


class AuthError(Exception):
    """Business-rule violation raised by ``AuthService``.

    Carries a human-readable ``message`` and a machine-readable ``code`` so
    that the HTTP layer can map it to the correct status code without
    hard-coding magic strings.

    The HTTP route layer is the *only* place that should catch this exception
    and convert it to an ``HTTPException``.  Nothing below the route layer
    (repository, service, utilities) should catch it.

    Attributes:
        message: A safe, user-facing error description.  Must not contain
            internal implementation details (stack traces, SQL, file paths).
        code: A short snake_case string identifying the failure type.
            Defined as class-level constants for exhaustive matching.

    Class constants (``code`` values):
        ``EMAIL_TAKEN``       — email already registered.
        ``INVALID_CREDENTIALS`` — wrong email or password.
        ``ACCOUNT_INACTIVE``  — account has been suspended.
        ``ACCOUNT_UNVERIFIED``— email not yet confirmed.
        ``INVALID_TOKEN``     — malformed / expired / wrong-type JWT.
        ``WRONG_PASSWORD``    — current password mismatch (password change).
        ``SAME_PASSWORD``     — new password identical to current one.
        ``USER_NOT_FOUND``    — UUID lookup returned nothing.

    Example::

        raise AuthError("Email already in use.", code=AuthError.EMAIL_TAKEN)
    """

    # ── Error code constants ─────────────────────────────────────────────── #
    EMAIL_TAKEN: str = "email_taken"
    INVALID_CREDENTIALS: str = "invalid_credentials"
    ACCOUNT_INACTIVE: str = "account_inactive"
    ACCOUNT_UNVERIFIED: str = "account_unverified"
    INVALID_TOKEN: str = "invalid_token"
    WRONG_PASSWORD: str = "wrong_password"
    SAME_PASSWORD: str = "same_password"
    USER_NOT_FOUND: str = "user_not_found"

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message: str = message
        self.code: str = code

    def __repr__(self) -> str:
        return f"AuthError(code={self.code!r}, message={self.message!r})"


# ─────────────────────────────────────────────────────────────────────────────
# AuthService
# ─────────────────────────────────────────────────────────────────────────────


class AuthService:
    """Orchestrates all authentication and credential-management workflows.

    ``AuthService`` is a **stateless**, request-scoped object.  Instantiate
    it once per request (or once per test case) with an active SQLAlchemy
    ``Session``.  Every public method is a self-contained unit-of-work:
    it validates inputs, delegates DB access to ``UserRepository``, commits
    on success, and raises ``AuthError`` on failure.

    Architecture guarantees:
        - Zero FastAPI imports — fully testable without a running HTTP server.
        - Zero raw SQL — all DB access goes through ``UserRepository``.
        - Zero password handling — delegates entirely to ``security.py``.
        - Raises ``AuthError`` (not ``HTTPException``) for all business-rule
          violations.

    Args:
        session: An active, open ``SQLAlchemy`` session.  The service commits
            on successful write operations.  The caller (route or fixture) is
            responsible for closing/rolling-back the session on failure.

    Example::

        svc = AuthService(db)
        user_response, tokens = svc.register_user(create_schema)
    """

    def __init__(self, session: Session) -> None:
        self._db: Session = session
        self._repo: UserRepository = UserRepository(session)

    # ── Factory helper ───────────────────────────────────────────────────── #

    @classmethod
    def from_session(cls, session: Session) -> "AuthService":
        """Convenience factory for creating an ``AuthService`` from a session.

        Equivalent to ``AuthService(session)`` but reads more naturally in
        dependency-injection contexts where the construction site and the type
        annotation are far apart.

        Args:
            session: An active SQLAlchemy ``Session``.

        Returns:
            A new ``AuthService`` bound to the given session.
        """
        return cls(session)

    # =========================================================================
    #  Internal helpers
    # =========================================================================

    def _assert_user_active(self, user: User) -> None:
        """Raise ``AuthError`` if the user's account is suspended.

        Args:
            user: The ORM ``User`` instance to check.

        Raises:
            AuthError: With code ``ACCOUNT_INACTIVE`` if ``user.is_active`` is
                ``False``.
        """
        if not user.is_active:
            logger.warning(
                "Auth attempt on suspended account | user_id=%s", user.id
            )
            raise AuthError(
                "This account has been suspended.  Please contact support.",
                code=AuthError.ACCOUNT_INACTIVE,
            )

    def _build_token_pair(self, user: User) -> TokenResponse:
        """Create a fresh access + refresh token pair for a user.

        Encodes the user's UUID as the JWT ``sub`` claim.  The UUIDs are
        coerced to ``str`` inside ``create_access_token`` / ``create_refresh_token``
        per their signatures.

        Args:
            user: The authenticated ``User`` ORM instance.

        Returns:
            A ``TokenResponse`` schema containing both signed JWTs and the
            ``token_type="bearer"`` field.
        """
        subject = str(user.id)
        return TokenResponse(
            access_token=create_access_token(subject=subject),
            refresh_token=create_refresh_token(subject=subject),
        )

    def _resolve_user_from_sub(self, sub: str) -> User:
        """Look up a ``User`` by the ``sub`` claim extracted from a JWT.

        Parses the ``sub`` string as a UUID and calls ``UserRepository.get_by_id``.

        Args:
            sub: The raw ``sub`` claim value from the decoded JWT payload.
                Expected to be a string representation of a UUID v4.

        Returns:
            The matching ``User`` ORM instance.

        Raises:
            AuthError: With code ``INVALID_TOKEN`` if ``sub`` cannot be parsed
                as a UUID.
            AuthError: With code ``USER_NOT_FOUND`` if no user with that UUID
                exists in the database.
        """
        try:
            user_id = uuid.UUID(str(sub))
        except (ValueError, AttributeError):
            logger.warning("decode_token returned non-UUID sub claim: %r", sub)
            raise AuthError(
                "Token contains an invalid subject claim.",
                code=AuthError.INVALID_TOKEN,
            )

        user = self._repo.get_by_id(user_id)
        if user is None:
            logger.warning("Token sub references unknown user | user_id=%s", user_id)
            raise AuthError(
                "The user associated with this token no longer exists.",
                code=AuthError.USER_NOT_FOUND,
            )
        return user

    # =========================================================================
    #  Public service methods
    # =========================================================================

    def register_user(
        self,
        payload: UserCreate,
    ) -> Tuple[UserResponse, TokenResponse]:
        """Register a new user account and issue an initial token pair.

        Workflow:
            1. Check that the email is not already registered.
            2. Hash the plain-text password using bcrypt.
            3. Persist the new user row via ``UserRepository.create_user``.
            4. Commit the transaction so the row is visible to other sessions.
            5. Generate and return an access + refresh token pair.

        The user's email is pre-normalised (lowercased, stripped) by the
        Pydantic ``UserCreate`` schema before reaching this method, ensuring
        consistent storage and lookup.

        New accounts are created with:
            - ``is_active = True`` (server default)
            - ``is_verified = False`` (email verification required)
            - ``role_id = None`` (role assigned during onboarding)

        Args:
            payload: A validated ``UserCreate`` schema containing
                ``full_name``, ``email``, and ``password`` (plain-text).

        Returns:
            A two-tuple of:
                - ``UserResponse``: The serialised user record (no password hash).
                - ``TokenResponse``: A fresh access + refresh JWT pair.

        Raises:
            AuthError: With code ``EMAIL_TAKEN`` if the email is already in use.

        Example::

            user_resp, tokens = svc.register_user(UserCreate(
                full_name="Alice Nguyen",
                email="alice@example.com",
                password="MyStr0ngP@ss!",
            ))
            db.commit()  # already committed inside; this is a no-op.
        """
        logger.info("register_user | email=%s", payload.email)

        # ── 1. Duplicate email guard ──────────────────────────────────────── #
        if self._repo.email_exists(payload.email):
            logger.warning("Registration blocked — email taken: %s", payload.email)
            raise AuthError(
                "An account with this email address already exists.",
                code=AuthError.EMAIL_TAKEN,
            )

        # ── 2. Hash password ──────────────────────────────────────────────── #
        pw_hash: str = hash_password(payload.password)

        # ── 3. Persist user ───────────────────────────────────────────────── #
        user: User = self._repo.create_user(
            full_name=payload.full_name,
            email=payload.email,
            password_hash=pw_hash,
        )

        # ── 4. Commit ─────────────────────────────────────────────────────── #
        self._db.commit()
        logger.info("User registered | user_id=%s | email=%s", user.id, user.email)

        # ── 5. Issue tokens ───────────────────────────────────────────────── #
        tokens: TokenResponse = self._build_token_pair(user)
        user_response: UserResponse = UserResponse.model_validate(user)
        return user_response, tokens

    def authenticate_user(self, email: str, password: str) -> User:
        """Verify credentials and return the authenticated ``User`` ORM instance.

        This is the low-level credential-verification primitive.  It does not
        issue tokens — use ``login_user`` for the full login workflow.

        Workflow:
            1. Look up the user by email.  A missing email returns the same
               generic error as a wrong password (avoids user-enumeration via
               timing differences — both paths call ``verify_password``).
            2. Verify the supplied password against the stored bcrypt hash.
               Passlib performs constant-time comparison.
            3. Assert the account is active.

        Args:
            email: The user's email address (pre-normalised).
            password: The plain-text password supplied by the caller.

        Returns:
            The authenticated, active ``User`` ORM instance.

        Raises:
            AuthError: With code ``INVALID_CREDENTIALS`` if the email does not
                exist or the password is incorrect.
            AuthError: With code ``ACCOUNT_INACTIVE`` if credentials are valid
                but the account is suspended.

        Example::

            user = svc.authenticate_user("alice@example.com", "MyStr0ngP@ss!")
        """
        logger.debug("authenticate_user | email=%s", email)

        user: Optional[User] = self._repo.get_by_email(email)

        # Always run verify_password even when the user is not found.
        # This prevents timing-based user-enumeration attacks: an attacker
        # measuring the response time cannot distinguish "no such user" from
        # "wrong password" because bcrypt work-factor cost is incurred either
        # way.  The dummy hash below is never verified successfully.
        dummy_hash = "$2b$12$notarealhashbutenoughlengthtopassvalidation123456789012"
        stored_hash: str = user.password_hash if user is not None else dummy_hash

        password_ok: bool = verify_password(password, stored_hash)

        if user is None or not password_ok:
            logger.warning("Auth failed — bad credentials | email=%s", email)
            raise AuthError(
                "Invalid email address or password.",
                code=AuthError.INVALID_CREDENTIALS,
            )

        self._assert_user_active(user)
        logger.info("authenticate_user success | user_id=%s", user.id)
        return user

    def login_user(self, payload: LoginRequest) -> Tuple[UserResponse, TokenResponse]:
        """Authenticate a user with email + password and return a full token pair.

        This is the primary entry point for the login endpoint.  It combines
        ``authenticate_user`` (credential verification) with ``_build_token_pair``
        (JWT issuance) and wraps the result in response schemas.

        Args:
            payload: A validated ``LoginRequest`` schema containing ``email``
                and ``password`` (plain-text).

        Returns:
            A two-tuple of:
                - ``UserResponse``: The serialised user record.
                - ``TokenResponse``: A fresh access + refresh JWT pair.

        Raises:
            AuthError: Any ``AuthError`` raised by ``authenticate_user``
                propagates unchanged.

        Example::

            user_resp, tokens = svc.login_user(LoginRequest(
                email="alice@example.com",
                password="MyStr0ngP@ss!",
            ))
        """
        logger.info("login_user | email=%s", payload.email)
        user: User = self.authenticate_user(payload.email, payload.password)
        tokens: TokenResponse = self._build_token_pair(user)
        user_response: UserResponse = UserResponse.model_validate(user)
        logger.info("login_user success | user_id=%s", user.id)
        return user_response, tokens

    def refresh_access_token(
        self, payload: RefreshTokenRequest
    ) -> AccessTokenResponse:
        """Issue a new access token from a valid refresh token.

        Workflow:
            1. Decode and cryptographically validate the refresh token via
               ``decode_token()`` (raises ``HTTPException`` on failure, which
               this service re-wraps as ``AuthError``).
            2. Assert the ``type`` claim equals ``"refresh"`` — prevents a
               client from submitting an access token to this endpoint.
            3. Resolve the user from the ``sub`` claim.
            4. Assert the account is still active.
            5. Issue and return a new access token only (not a new refresh
               token — full token rotation is a service-layer enhancement).

        Args:
            payload: A validated ``RefreshTokenRequest`` schema containing
                the raw refresh JWT string.

        Returns:
            An ``AccessTokenResponse`` containing a freshly signed access token
            and ``token_type="bearer"``.

        Raises:
            AuthError: With code ``INVALID_TOKEN`` if the token is expired,
                tampered, structurally invalid, or not of type ``"refresh"``.
            AuthError: With code ``ACCOUNT_INACTIVE`` if the user account has
                been suspended since the refresh token was issued.
            AuthError: With code ``USER_NOT_FOUND`` if the user no longer
                exists in the database.

        Example::

            new_token = svc.refresh_access_token(
                RefreshTokenRequest(refresh_token="eyJ...")
            )
        """
        logger.debug("refresh_access_token called")

        # ── 1. Decode & verify cryptographic validity ─────────────────────── #
        # decode_token() raises HTTPException on failure (expired / invalid).
        # We catch that and re-raise as AuthError to maintain the no-FastAPI
        # boundary of this service.
        from fastapi import HTTPException  # local import — kept out of module scope

        try:
            raw_payload: dict = decode_token(payload.refresh_token)
        except HTTPException as exc:
            logger.warning("refresh_access_token — token decode failed: %s", exc.detail)
            raise AuthError(
                exc.detail,
                code=AuthError.INVALID_TOKEN,
            ) from exc

        # ── 2. Validate token type ────────────────────────────────────────── #
        token_data = TokenPayload(**raw_payload)
        if token_data.type != "refresh":
            logger.warning(
                "refresh_access_token — wrong token type submitted: %s",
                token_data.type,
            )
            raise AuthError(
                "A refresh token is required for this operation.",
                code=AuthError.INVALID_TOKEN,
            )

        # ── 3 & 4. Resolve user and check active status ───────────────────── #
        user: User = self._resolve_user_from_sub(str(token_data.sub))
        self._assert_user_active(user)

        # ── 5. Issue new access token ─────────────────────────────────────── #
        new_access_token: str = create_access_token(subject=str(user.id))
        logger.info("refresh_access_token success | user_id=%s", user.id)
        return AccessTokenResponse(access_token=new_access_token)

    def change_password(
        self,
        user_id: uuid.UUID,
        payload: PasswordChangeRequest,
    ) -> UserResponse:
        """Change an authenticated user's password.

        Workflow:
            1. Load the user from the database.
            2. Assert the account is active.
            3. Verify the supplied ``current_password`` against the stored hash.
            4. Reject if the new password is identical to the current one.
               (The Pydantic schema also validates this, but re-checking here
               guards against future schema changes.)
            5. Hash the new password and persist the updated user row.
            6. Commit the transaction.

        Args:
            user_id: UUID of the authenticated user requesting the change.
            payload: A validated ``PasswordChangeRequest`` schema containing
                ``current_password``, ``new_password``, and ``confirm_password``.
                The schema already validates that the two new-password fields
                match and differ from the current one.

        Returns:
            A ``UserResponse`` reflecting the updated user record.

        Raises:
            AuthError: With code ``USER_NOT_FOUND`` if the user_id does not
                match any database row (should not happen for authenticated
                users, but guards against race conditions).
            AuthError: With code ``ACCOUNT_INACTIVE`` if the account is
                suspended.
            AuthError: With code ``WRONG_PASSWORD`` if ``current_password``
                does not match the stored hash.
            AuthError: With code ``SAME_PASSWORD`` if the new password is
                identical to the current one.

        Example::

            updated = svc.change_password(
                current_user.id,
                PasswordChangeRequest(
                    current_password="OldP@ss1",
                    new_password="NewStr0ng!",
                    confirm_password="NewStr0ng!",
                ),
            )
        """
        logger.info("change_password | user_id=%s", user_id)

        # ── 1. Load user ──────────────────────────────────────────────────── #
        user: Optional[User] = self._repo.get_by_id(user_id)
        if user is None:
            raise AuthError(
                "User not found.",
                code=AuthError.USER_NOT_FOUND,
            )

        # ── 2. Active check ───────────────────────────────────────────────── #
        self._assert_user_active(user)

        # ── 3. Verify current password ────────────────────────────────────── #
        if not verify_password(payload.current_password, user.password_hash):
            logger.warning(
                "change_password — wrong current password | user_id=%s", user_id
            )
            raise AuthError(
                "The current password you entered is incorrect.",
                code=AuthError.WRONG_PASSWORD,
            )

        # ── 4. Guard: new == current ──────────────────────────────────────── #
        # verify_password performs bcrypt comparison — if the new password
        # matches the current hash, they are identical.
        if verify_password(payload.new_password, user.password_hash):
            raise AuthError(
                "The new password must differ from the current password.",
                code=AuthError.SAME_PASSWORD,
            )

        # ── 5. Hash & persist ─────────────────────────────────────────────── #
        new_hash: str = hash_password(payload.new_password)
        self._repo.update_user(user, password_hash=new_hash)

        # ── 6. Commit ─────────────────────────────────────────────────────── #
        self._db.commit()
        logger.info("Password changed | user_id=%s", user_id)
        return UserResponse.model_validate(user)

    def get_current_user_by_token(self, token: str) -> UserResponse:
        """Validate an access token and return the corresponding user.

        This is the primary FastAPI dependency helper.  The route layer calls
        this method with the raw Bearer token string extracted from the
        ``Authorization`` header.

        Workflow:
            1. Cryptographically decode and verify the token.
            2. Assert the ``type`` claim equals ``"access"`` — prevents refresh
               tokens from being accepted on protected API routes.
            3. Parse ``sub`` as a UUID and load the user from the database.
            4. Assert the account is active.
            5. Return the serialised user record.

        Args:
            token: The raw JWT string extracted from the ``Authorization:
                Bearer <token>`` header (without the ``Bearer `` prefix).

        Returns:
            A ``UserResponse`` schema representing the authenticated,
            active user.

        Raises:
            AuthError: With code ``INVALID_TOKEN`` if the token is expired,
                tampered, structurally invalid, or of type ``"refresh"`` instead
                of ``"access"``.
            AuthError: With code ``USER_NOT_FOUND`` if the ``sub`` claim points
                to a non-existent user.
            AuthError: With code ``ACCOUNT_INACTIVE`` if the user account has
                been suspended.

        Example::

            # In a FastAPI dependency:
            from fastapi.security import OAuth2PasswordBearer

            oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

            def get_current_user(
                token: str = Depends(oauth2_scheme),
                db: Session = Depends(get_db),
            ) -> UserResponse:
                svc = AuthService(db)
                return svc.get_current_user_by_token(token)
        """
        logger.debug("get_current_user_by_token called")

        from fastapi import HTTPException  # local import — kept out of module scope

        # ── 1. Decode token ───────────────────────────────────────────────── #
        try:
            raw_payload: dict = decode_token(token)
        except HTTPException as exc:
            logger.warning("get_current_user_by_token — decode failed: %s", exc.detail)
            raise AuthError(
                exc.detail,
                code=AuthError.INVALID_TOKEN,
            ) from exc

        # ── 2. Validate token type ────────────────────────────────────────── #
        token_data = TokenPayload(**raw_payload)
        if token_data.type != "access":
            logger.warning(
                "get_current_user_by_token — wrong type: %s", token_data.type
            )
            raise AuthError(
                "An access token is required for this operation.",
                code=AuthError.INVALID_TOKEN,
            )

        # ── 3 & 4. Resolve user and check active status ───────────────────── #
        user: User = self._resolve_user_from_sub(str(token_data.sub))
        self._assert_user_active(user)

        logger.debug("get_current_user_by_token success | user_id=%s", user.id)
        return UserResponse.model_validate(user)
