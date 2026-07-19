"""
backend/app/models/user.py
---------------------------
ORM model for the `users` table.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT THIS FILE DEFINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • The `User` ORM model (SQLAlchemy 2.x `DeclarativeBase` style).
  • Table: `users`
  • Relationship: many Users → one Role  (back-populated on Role.users)

  This file contains ONLY the ORM model — no authentication logic,
  no password hashing, no JWT handling.  Those concerns live in:
    • app/core/security.py  — password hashing / JWT utilities
    • app/services/auth.py  — authentication business logic
    • app/api/v1/auth/      — HTTP endpoints

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COLUMN OVERVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  id            UUID PRIMARY KEY — Python-generated (uuid4); PK is known
                before the INSERT reaches the database.

  role_id       UUID FK → roles.id NULLABLE — a NULL role_id means the user
                has no role assigned yet (e.g. pending onboarding).
                ON DELETE SET NULL: deleting a Role nullifies this field
                rather than deleting the user row.

  full_name     VARCHAR(255) NOT NULL — display name, not a login identifier.

  email         VARCHAR(255) UNIQUE NOT NULL — login identifier.
                RFC 5321 max is 254 chars; 255 is the universal safe choice.

  password_hash VARCHAR(255) NOT NULL — bcrypt / argon2 hash of the
                password.  Never the plaintext.  Hashing is performed by
                app/core/security.py, not here.

  is_active     BOOLEAN NOT NULL DEFAULT true — soft-delete flag.  Inactive
                users cannot log in.  Prefer this over hard-deleting rows to
                preserve referential integrity with other tables.

  is_verified   BOOLEAN NOT NULL DEFAULT false — email-verification gate.
                Set to true once the user confirms their email address.

  created_at    TIMESTAMP WITH TIME ZONE — set server-side by PostgreSQL at
                INSERT time; never changes after creation.

  updated_at    TIMESTAMP WITH TIME ZONE — set server-side at INSERT and
                refreshed automatically on every UPDATE.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INDEXES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ix_users_email          UNIQUE — implicit from unique=True on `email`.
                          Speeds up every login / lookup-by-email query.

  ix_users_full_name      B-tree — admin search and ORDER BY name.

  ix_users_role_id        B-tree — speeds up `JOIN roles ON users.role_id`.

  ix_users_is_active      B-tree — almost every query filters active users.

  ix_users_email_active   COMPOSITE (email, is_active) — the most common
                          real-world auth query pattern:
                              WHERE email = ? AND is_active = true
                          A composite index answers this in one index scan
                          without touching the heap for is_active.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESIGN DECISIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • `password_hash` naming: makes it impossible to accidentally log the
    column and leak a plaintext password — the name itself is a reminder.

  • Nullable role_id (+ ON DELETE SET NULL): prevents accidental user
    deletion when a Role is removed.  Aligns with role.py's decision not
    to use cascade="all, delete-orphan".

  • server_default for booleans: ensures is_active/is_verified are correct
    even for bulk SQL inserts that bypass Python-layer defaults.

  • TYPE_CHECKING guard on Role: prevents the runtime circular import
    between user.py ↔ role.py while keeping full type-checker support.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGISTRATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Registered in app/db/base.py:
      from app.models.user import User  # noqa: F401
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# ── TYPE_CHECKING guard ───────────────────────────────────────────────────── #
# `Role` is imported ONLY for static analysis (mypy / pyright / IDEs).
# At runtime this block is never executed, which breaks the circular import
# chain:  user.py imports base.py ← base.py imports role.py ← role.py uses
# TYPE_CHECKING to import user.py.  Only the type checker sees both sides.
if TYPE_CHECKING:
    from app.models.role import Role


# =========================================================================== #
#  User ORM model                                                               #
# =========================================================================== #

class User(Base):
    """
    Represents a registered user account.

    Stores identity and credential data only — no session state, no tokens,
    no business-domain attributes.  Those are tracked in related tables
    (interviews, tasks, resumes, etc.).

    A User belongs to at most one :class:`~app.models.role.Role`.  The ``role``
    relationship gives direct ORM access to the role object; ``role_id`` is the
    raw FK column used in queries and constraints.

    Table
    -----
    ``users``

    Relationships
    -------------
    role : Role | None
        The role assigned to this user, or ``None`` if no role has been
        assigned yet.  Back-populated by ``Role.users``.
    """

    __tablename__ = "users"

    # ── Table-level constraints and composite indexes ─────────────────────── #
    # Composite indexes that span more than one column MUST be declared here
    # in __table_args__ — they cannot be expressed inside a single
    # mapped_column() call.
    #
    # ix_users_email_active covers the most common auth lookup pattern:
    #     SELECT * FROM users WHERE email = ? AND is_active = true
    # PostgreSQL resolves this in a single index scan without a heap fetch
    # for is_active, making it dramatically faster than two separate indexes
    # at scale (millions of users).
    __table_args__ = (
        Index(
            "ix_users_email_active",   # Explicit index name — survives renames.
            "email",
            "is_active",
            # not a unique index — email alone is unique, but the composite
            # is purely a performance index, not a constraint.
        ),
    )

    # ── Primary key ──────────────────────────────────────────────────────── #
    # Same pattern as Role.id — Python-generated UUID4 so the PK is
    # available before the DB INSERT, enabling log correlation and test
    # assertions without a round-trip.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,     # Callable reference — fresh UUID per row.
        nullable=False,
        comment="Surrogate primary key.  Generated by Python (UUID v4).",
    )

    # ── Foreign key — role ────────────────────────────────────────────────── #
    # Nullable: a user with no role is valid (e.g. just registered and
    # awaiting role assignment during onboarding).
    #
    # ondelete="SET NULL": if the referenced Role row is deleted by a DBA or
    # an admin action, PostgreSQL automatically sets this column to NULL
    # instead of raising a FK violation or (worse) cascade-deleting the user.
    # This is the safest production default for optional FK references.
    #
    # index=True: the FK column gets its own B-tree index so that:
    #   • JOIN users ON role_id = roles.id  is served by an index seek.
    #   • Queries that filter by role_id don't require a full table scan.
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "roles.id",
            ondelete="SET NULL",    # Nullify, do NOT delete the user.
            name="fk_users_role_id",  # Explicit constraint name — easier to
                                       # reference in migrations and error msgs.
        ),
        nullable=True,
        index=True,                 # B-tree index for JOIN performance.
        default=None,
        comment=(
            "FK → roles.id.  NULL means no role assigned yet.  "
            "SET NULL on role deletion."
        ),
    )

    # ── Full name ─────────────────────────────────────────────────────────── #
    # Display name for UI rendering.  Not a login identifier.
    # VARCHAR(255) covers the widest realistic personal name including
    # honorifics and multi-part surnames (e.g. "Dr. María García López").
    # index=True enables fast admin search (LIKE 'Garcia%') and ORDER BY.
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="User's display name.  Not unique — two users may share a name.",
    )

    # ── Email ─────────────────────────────────────────────────────────────── #
    # Primary login credential and communication address.
    # RFC 5321 caps email length at 254 characters; 255 is universally safe.
    #
    # unique=True creates both:
    #   • A UNIQUE constraint (raises IntegrityError on duplicate insert).
    #   • An implicit B-tree index named ix_users_email (PostgreSQL convention).
    # No separate `index=True` is needed — the unique constraint IS the index.
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment=(
            "Primary login identifier.  RFC 5321 max 254 chars.  "
            "Unique across the entire platform."
        ),
    )

    # ── Password hash ─────────────────────────────────────────────────────── #
    # Stores the output of a password hashing algorithm (bcrypt / argon2id).
    # Naming this field `password_hash` (not `password`) makes it instantly
    # clear to any reader — human or linter — that this is NOT plaintext.
    #
    # bcrypt output: 60 chars.  argon2id output: up to ~120 chars.
    # String(255) covers both current and foreseeable future algorithms.
    #
    # String (VARCHAR) is preferred over Text here because:
    #   • The value length is bounded (hashes are fixed-length per algorithm).
    #   • PostgreSQL stores VARCHAR(n) values inline (no TOAST overhead).
    #   • The column can be included in covering indexes if needed.
    #
    # Authentication logic (hashing, verification) lives in:
    #   app/core/security.py — NOT in this model.
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment=(
            "bcrypt/argon2 hash of the user's password.  "
            "NEVER stores plaintext.  Hashing is performed in app/core/security.py."
        ),
    )

    # ── is_active ─────────────────────────────────────────────────────────── #
    # Soft-delete / account suspension flag.
    # True (default) = account is usable.
    # False          = account is suspended / deactivated.
    #
    # Soft-delete is preferred over hard-delete in production because:
    #   • Other tables (interviews, resumes, tasks) have FK references to
    #     users.id.  Hard-deleting a user would require cascading or
    #     nullable FK updates across many tables.
    #   • Audit trails remain intact — deleted users are still traceable.
    #   • Recovery is trivial: flip is_active back to True.
    #
    # server_default="true": DB evaluates this at INSERT time.  Ensures
    # correctness even for bulk inserts that bypass Python defaults.
    #
    # index=True: nearly every authenticated query filters
    #   WHERE is_active = true — without an index this is a full table scan.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",  # DB-level default for raw SQL inserts.
        index=True,
        comment="False = account suspended.  Prefer over hard-deleting user rows.",
    )

    # ── is_verified ───────────────────────────────────────────────────────── #
    # Email-verification gate.
    # False (default) = user has not confirmed their email address yet.
    # True            = email confirmed; full platform access granted.
    #
    # The verification flow (token generation, email sending, token check)
    # lives in app/services/auth.py — not here.
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",  # DB-level default for raw SQL inserts.
        comment=(
            "True once the user has confirmed their email address.  "
            "Unverified users may have restricted access depending on policy."
        ),
    )

    # ── Timestamps ───────────────────────────────────────────────────────── #
    # Identical pattern to role.py: TIMESTAMP WITH TIME ZONE ensures
    # PostgreSQL stores UTC regardless of the server's local timezone.
    # func.now() is evaluated server-side at INSERT/UPDATE time.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="UTC timestamp of account creation.  Immutable after INSERT.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # Set on INSERT.
        onupdate=func.now(),        # Refreshed on every UPDATE automatically.
        comment="UTC timestamp of the last modification to this user row.",
    )

    # =========================================================================
    #  Relationships
    # =========================================================================

    # ── Many Users → One Role ─────────────────────────────────────────────── #
    # This is the reverse side of Role.users.
    # `back_populates="users"` must match the attribute name on Role exactly —
    # SQLAlchemy validates this at mapper configuration time and raises a clear
    # error if there is a mismatch.
    #
    # `lazy="select"` (default): the Role is loaded with a separate SELECT
    # the first time `user.role` is accessed.  Callers that need the Role
    # eagerly can opt in at the query level:
    #     session.execute(select(User).options(selectinload(User.role)))
    #
    # foreign_keys=[role_id] is specified explicitly to disambiguate the FK
    # when multiple FK columns point to the same table (not the case now, but
    # declaring it prevents a SQLAlchemy AmbiguousForeignKeysError if a second
    # FK to `roles` is ever added).
    role: Mapped["Role | None"] = relationship(
        "Role",
        back_populates="users",
        foreign_keys=[role_id],
        lazy="select",
        doc="The role assigned to this user, or None if no role has been assigned.",
    )

    # =========================================================================
    #  Dunder methods
    # =========================================================================

    def __repr__(self) -> str:
        """
        Unambiguous developer representation.

        Shown in debugger watches, log lines, and test failure messages.
        Includes PK and email so log lines are self-contained.
        Deliberately omits password_hash — it must never appear in logs.
        """
        return (
            f"User("
            f"id={self.id!r}, "
            f"email={self.email!r}, "
            f"is_active={self.is_active!r}, "
            f"is_verified={self.is_verified!r}"
            f")"
        )

    def __str__(self) -> str:
        """
        Human-readable string representation.

        Returns the user's display name — used in template rendering,
        admin UI labels, and f-string logging.
        """
        return self.full_name
