"""
backend/app/repositories/user.py
=================================
Repository pattern implementation for the ``users`` table.

This module is the **sole** layer that issues SQL against the ``users`` table.
It has exactly one responsibility: translate Python method calls into
SQLAlchemy 2.x queries and return ORM ``User`` objects.

Architecture contract
---------------------
* **No business logic** — validation, policy decisions, and orchestration
  belong in ``app/services/``.
* **No password hashing or JWT** — those live in ``app/core/security.py``.
* **No FastAPI imports** — no ``HTTPException``, no ``Depends``, no ``Request``.
  This keeps the repository testable without spinning up a web server.
* **Session ownership** — the caller (service or route via ``Depends(get_db)``)
  owns the session lifecycle (commit / rollback / close).  The repository
  *never* commits or closes the session it receives.  It does call
  ``session.flush()`` after mutating operations so that DB-generated values
  (e.g. server-side timestamps) are reflected on the returned ORM object
  before the caller decides whether to commit.
* **Rollback on failure** — every mutating method wraps its core work in a
  ``try/except`` that rolls back and re-raises on ``SQLAlchemyError``, keeping
  the session in a clean state for the caller's exception handler.

Transaction strategy
--------------------
SQLAlchemy 2.x (with ``autocommit=False``) starts an implicit transaction on
the first statement.  The repository calls ``session.flush()`` — not
``session.commit()`` — so that:

  1. DB constraints are evaluated and ``IntegrityError`` is surfaced early.
  2. Auto-generated column values (``server_default``, sequences) are written
     back to the ORM object.
  3. The caller retains full control: it can still roll back the entire
     unit-of-work (e.g. if a second write fails after this one succeeded).

Usage example
-------------
::

    # In a service method:
    from sqlalchemy.orm import Session
    from app.repositories.user import UserRepository

    def register(db: Session, full_name: str, email: str, pw_hash: str):
        repo = UserRepository(db)
        if repo.email_exists(email):
            raise ValueError("Email already registered.")
        return repo.create_user(full_name=full_name, email=email, password_hash=pw_hash)
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.user import User

logger: logging.Logger = logging.getLogger(__name__)


class UserRepository:
    """Data-access layer for the ``users`` table.

    Every public method corresponds to a single, well-defined query or DML
    statement.  All methods receive their data as plain Python values and
    return either a ``User`` ORM instance, a list of ``User`` instances, or a
    primitive (``bool``).

    The repository is stateless apart from the injected ``Session`` reference,
    making it safe to instantiate once per request inside a FastAPI dependency
    or service method.

    Args:
        session: An active SQLAlchemy ``Session`` bound to the application's
            engine.  The caller is responsible for committing or rolling back
            the session after the repository method returns.

    Example::

        repo = UserRepository(db)
        user = repo.get_by_email("alice@example.com")
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # =========================================================================
    #  Read operations
    # =========================================================================

    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Fetch a single user by their UUID primary key.

        Uses ``Session.get`` which hits the identity map first (returning a
        cached object if the same PK was already loaded in this session) and
        falls back to a ``SELECT`` against the ``users`` table only if needed.
        This is the most efficient single-row lookup available in SQLAlchemy.

        Args:
            user_id: The UUID primary key of the user to retrieve.

        Returns:
            The matching ``User`` ORM instance, or ``None`` if no row with
            the given PK exists in the database.

        Example::

            user = repo.get_by_id(uuid.UUID("550e8400-e29b-41d4-a716-446655440000"))
            if user is None:
                raise ValueError("User not found.")
        """
        logger.debug("get_by_id | user_id=%s", user_id)
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        """Fetch a single user by their email address.

        Performs a case-sensitive equality match against the ``users.email``
        column.  Because the column carries a ``UNIQUE`` constraint, the
        result set can contain at most one row.

        The query is served by the implicit ``ix_users_email`` index created
        by SQLAlchemy when ``unique=True`` is set on the column, making this
        an O(log n) index seek rather than a full table scan.

        Args:
            email: The email address to look up.  Must be pre-normalised
                (lowercased, stripped) by the schema layer before this method
                is called — the repository performs no normalisation.

        Returns:
            The matching ``User`` ORM instance, or ``None`` if no row with
            the given email exists.

        Example::

            user = repo.get_by_email("alice@example.com")
        """
        logger.debug("get_by_email | email=%s", email)
        stmt = select(User).where(User.email == email)
        return self._session.execute(stmt).scalar_one_or_none()

    def email_exists(self, email: str) -> bool:
        """Check whether an email address is already registered.

        Executes a lightweight ``SELECT 1 … LIMIT 1`` style existence query
        rather than fetching the full row, making it cheaper than
        ``get_by_email`` when only a boolean answer is needed (e.g. during
        registration pre-validation).

        Args:
            email: The email address to test.  Must be pre-normalised
                (lowercased, stripped) by the schema layer.

        Returns:
            ``True`` if at least one active or inactive user row with this
            email exists, ``False`` otherwise.

        Example::

            if repo.email_exists("alice@example.com"):
                raise ValueError("Email already in use.")
        """
        logger.debug("email_exists | email=%s", email)
        stmt = select(func.count()).select_from(User).where(User.email == email)
        count: int = self._session.execute(stmt).scalar_one()
        return count > 0

    def list_users(
        self,
        *,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """Return a paginated list of users, optionally filtered by active status.

        Results are ordered by ``created_at`` ascending (oldest accounts first)
        to provide a stable, deterministic page order that does not shift as
        new users are added.

        Args:
            is_active: When ``True``, return only active (non-suspended) users.
                When ``False``, return only suspended users.  When ``None``
                (default), return all users regardless of status.
            skip: Number of rows to skip (0-indexed offset).  Use with
                ``limit`` to implement page-based or cursor-based pagination.
                Must be >= 0.
            limit: Maximum number of rows to return per page.  Must be
                between 1 and 1000 (enforced by the service/schema layer,
                not here).  Defaults to 100.

        Returns:
            A (possibly empty) list of ``User`` ORM instances ordered by
            ``created_at`` ascending.

        Example::

            # First 50 active users
            active = repo.list_users(is_active=True, skip=0, limit=50)

            # All users (no filter)
            everyone = repo.list_users()
        """
        logger.debug(
            "list_users | is_active=%s | skip=%d | limit=%d",
            is_active,
            skip,
            limit,
        )
        stmt = select(User).order_by(User.created_at.asc())

        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        stmt = stmt.offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    # =========================================================================
    #  Write operations
    # =========================================================================

    def create_user(
        self,
        *,
        full_name: str,
        email: str,
        password_hash: str,
        role_id: Optional[uuid.UUID] = None,
    ) -> User:
        """Persist a new user row and return the ORM instance.

        Constructs a ``User`` ORM object, adds it to the session's identity
        map, and flushes so that server-side defaults (``created_at``,
        ``updated_at``, ``is_active``, ``is_verified``) are written back to
        the object.  The caller must commit the session to make the row
        visible to other database connections.

        The ``id`` column is Python-generated (``uuid.uuid4``), so the new
        user's PK is available on the returned object immediately — no DB
        round-trip is required to discover it.

        Args:
            full_name: The user's display name (1–255 characters).
            email: The user's email address, pre-normalised to lowercase by
                the schema layer.  Must not already exist in the database;
                if it does an ``IntegrityError`` is raised and re-raised after
                rollback.
            password_hash: The bcrypt/argon2 hash of the user's password.
                Must be produced by ``app/core/security.hash_password()`` —
                never a plain-text password.
            role_id: Optional UUID of an existing role to assign immediately.
                ``None`` (default) leaves the user without a role
                (``users.role_id IS NULL``).

        Returns:
            The freshly created ``User`` ORM instance with all DB-populated
            fields resolved (id, timestamps, booleans).

        Raises:
            sqlalchemy.exc.IntegrityError: If the email already exists in the
                database (unique constraint violation).  The session is rolled
                back before the exception propagates.
            sqlalchemy.exc.SQLAlchemyError: For any other database-level error.
                The session is rolled back before the exception propagates.

        Example::

            from app.core.security import hash_password
            user = repo.create_user(
                full_name="Alice Nguyen",
                email="alice@example.com",
                password_hash=hash_password("MyStr0ngP@ss!"),
            )
            db.commit()
        """
        logger.debug("create_user | email=%s | role_id=%s", email, role_id)
        user = User(
            full_name=full_name,
            email=email,
            password_hash=password_hash,
            role_id=role_id,
        )
        try:
            self._session.add(user)
            self._session.flush()   # Resolves server_defaults; surfaces IntegrityError early.
            logger.info("User created | id=%s | email=%s", user.id, user.email)
            return user
        except IntegrityError:
            logger.warning("create_user failed — duplicate email: %s", email)
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("create_user failed — unexpected DB error | email=%s", email)
            self._session.rollback()
            raise

    def update_user(
        self,
        user: User,
        *,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        password_hash: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
    ) -> User:
        """Apply a partial update to an existing user row.

        Follows PATCH semantics: only the keyword arguments that are **not**
        ``None`` are applied.  This allows the caller to change a single field
        without needing to supply every other field.

        The method mutates the ORM object in-place (SQLAlchemy tracks the
        changes automatically in the unit-of-work) and then flushes so that
        the ``updated_at`` server-side trigger fires and the object reflects
        the current DB state.

        Args:
            user: The ``User`` ORM instance to update.  Must already be
                attached to this session (loaded in the same session or merged).
            full_name: New display name, or ``None`` to leave unchanged.
            email: New email address (pre-normalised), or ``None`` to leave
                unchanged.  The unique constraint is enforced at flush time.
            password_hash: New bcrypt/argon2 hash, or ``None`` to leave
                unchanged.  Never pass a plain-text password here.
            is_active: New activation status, or ``None`` to leave unchanged.
            is_verified: New verification status, or ``None`` to leave
                unchanged.

        Returns:
            The same ``User`` ORM instance with updated fields reflected.

        Raises:
            sqlalchemy.exc.IntegrityError: If the new email conflicts with an
                existing user.  Session is rolled back before propagation.
            sqlalchemy.exc.SQLAlchemyError: For any other database-level error.
                Session is rolled back before propagation.

        Example::

            user = repo.get_by_id(user_id)
            updated = repo.update_user(user, full_name="Alice M. Nguyen")
            db.commit()
        """
        logger.debug("update_user | id=%s", user.id)

        if full_name is not None:
            user.full_name = full_name
        if email is not None:
            user.email = email
        if password_hash is not None:
            user.password_hash = password_hash
        if is_active is not None:
            user.is_active = is_active
        if is_verified is not None:
            user.is_verified = is_verified

        try:
            self._session.flush()
            logger.info("User updated | id=%s", user.id)
            return user
        except IntegrityError:
            logger.warning("update_user failed — unique constraint violation | id=%s", user.id)
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception("update_user failed — unexpected DB error | id=%s", user.id)
            self._session.rollback()
            raise

    def soft_delete_user(self, user: User) -> User:
        """Deactivate a user account without removing the database row.

        Sets ``is_active = False``, making the account inaccessible to login
        and most application queries while preserving the row for audit trails,
        analytics, and foreign-key integrity (other tables reference
        ``users.id``).

        Hard-deleting user rows is deliberately not supported in this
        repository because cascading FK updates across interviews, resumes,
        and tasks would be error-prone and irreversible.

        Args:
            user: The ``User`` ORM instance to deactivate.  Must be attached
                to this session.

        Returns:
            The same ``User`` ORM instance with ``is_active=False`` reflected.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On any database-level failure.
                Session is rolled back before propagation.

        Example::

            user = repo.get_by_id(user_id)
            repo.soft_delete_user(user)
            db.commit()
        """
        logger.debug("soft_delete_user | id=%s", user.id)
        user.is_active = False
        try:
            self._session.flush()
            logger.info("User soft-deleted | id=%s | email=%s", user.id, user.email)
            return user
        except SQLAlchemyError:
            logger.exception("soft_delete_user failed | id=%s", user.id)
            self._session.rollback()
            raise

    def assign_role(self, user: User, role_id: Optional[uuid.UUID]) -> User:
        """Assign or unassign a role from a user.

        Sets the ``role_id`` FK column to the provided value.  Passing
        ``None`` removes the current role assignment, returning the user to
        the unassigned state (useful during role migration or admin cleanup).

        The FK constraint (``fk_users_role_id``) is enforced by PostgreSQL at
        flush time — if the provided ``role_id`` does not correspond to a row
        in ``roles``, an ``IntegrityError`` is raised.

        Args:
            user: The ``User`` ORM instance to modify.  Must be attached to
                this session.
            role_id: UUID of an existing role to assign, or ``None`` to
                remove the current role assignment.

        Returns:
            The same ``User`` ORM instance with ``role_id`` updated.

        Raises:
            sqlalchemy.exc.IntegrityError: If ``role_id`` does not reference
                an existing row in the ``roles`` table.  Session is rolled
                back before propagation.
            sqlalchemy.exc.SQLAlchemyError: For any other database-level error.
                Session is rolled back before propagation.

        Example::

            admin_role_id = uuid.UUID("...")
            user = repo.get_by_id(user_id)
            repo.assign_role(user, admin_role_id)
            db.commit()

            # Remove role:
            repo.assign_role(user, None)
            db.commit()
        """
        logger.debug("assign_role | user_id=%s | role_id=%s", user.id, role_id)
        user.role_id = role_id
        try:
            self._session.flush()
            logger.info(
                "Role assigned | user_id=%s | role_id=%s",
                user.id,
                role_id,
            )
            return user
        except IntegrityError:
            logger.warning(
                "assign_role failed — role_id does not exist | user_id=%s | role_id=%s",
                user.id,
                role_id,
            )
            self._session.rollback()
            raise
        except SQLAlchemyError:
            logger.exception(
                "assign_role failed — unexpected DB error | user_id=%s", user.id
            )
            self._session.rollback()
            raise
