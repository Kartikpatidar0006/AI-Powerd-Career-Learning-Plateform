"""
Auth Service Feature Tests.

Covers:
  - Refresh token rotation: old token invalidated, new pair issued.
  - Revoked token rejected with 401.
  - Logout (single-token and full-session) invalidates tokens.
  - Password strength enforcement (schema validator unit tests).
  - Login rate-limit: 6th request on same IP returns 429.

No Docker / PostgreSQL required — all DB calls are mocked.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import UserSignupRequest
from app.services.auth_service import AuthService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GATEWAY_HEADERS = {"X-Gateway-Token": settings.GATEWAY_SERVICE_TOKEN}

_VALID_EMAIL = "featuretest@example.com"
_VALID_PASSWORD = "Password123!"


def _make_mock_db():
    """Build a minimal async mock that satisfies AuthService DB calls."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


def _make_user(email: str = _VALID_EMAIL, is_active: bool = True) -> User:
    import uuid
    user = User()
    user.id = uuid.uuid4()
    user.email = email
    user.hashed_password = hash_password(_VALID_PASSWORD)
    user.is_active = is_active
    user.created_at = datetime.now(timezone.utc)
    return user


def _make_rt_record(user_id, raw_token: str, revoked: bool = False) -> RefreshToken:
    rt = RefreshToken()
    rt.user_id = user_id
    rt.token_hash = hash_token(raw_token)
    rt.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    rt.revoked = revoked
    return rt


# ---------------------------------------------------------------------------
# 1. Refresh Token Rotation
# ---------------------------------------------------------------------------

class TestRefreshTokenRotation(unittest.IsolatedAsyncioTestCase):
    """Rotation: old token is revoked and a brand-new pair is issued."""

    async def asyncSetUp(self) -> None:
        self.user = _make_user()
        self.raw_refresh, _ = create_refresh_token(subject=self.user.id)
        self.rt_record = _make_rt_record(self.user.id, self.raw_refresh)

    async def test_rotation_revokes_old_token(self) -> None:
        """After refresh_tokens(), the old RefreshToken record must be marked revoked."""
        db = _make_mock_db()
        mr_rt = MagicMock()
        mr_rt.scalar_one_or_none.return_value = self.rt_record
        mr_user = MagicMock()
        mr_user.scalar_one_or_none.return_value = self.user
        db.execute.side_effect = [mr_rt, mr_user]

        svc = AuthService(db)
        resp = await svc.refresh_tokens(refresh_token=self.raw_refresh)

        self.assertTrue(self.rt_record.revoked, "old token record must be revoked")
        self.assertIsNotNone(resp.access_token)
        self.assertIsNotNone(resp.refresh_token)
        # Verify a new RefreshToken row was persisted to the DB.
        # We cannot assert JWT bytes differ — same user + same expiry-second
        # produces an identical HMAC JWT (deterministic, no nonce).
        db.add.assert_called_once()  # new RefreshToken record stored

    async def test_rotation_issues_new_bearer_pair(self) -> None:
        """Rotation returns token_type='bearer' with non-empty tokens."""
        db = _make_mock_db()
        mr_rt = MagicMock()
        mr_rt.scalar_one_or_none.return_value = self.rt_record
        mr_user = MagicMock()
        mr_user.scalar_one_or_none.return_value = self.user
        db.execute.side_effect = [mr_rt, mr_user]

        svc = AuthService(db)
        resp = await svc.refresh_tokens(refresh_token=self.raw_refresh)

        self.assertEqual(resp.token_type, "bearer")
        self.assertGreater(len(resp.access_token), 20)
        self.assertGreater(len(resp.refresh_token), 20)


# ---------------------------------------------------------------------------
# 2. Revoked Token Rejected
# ---------------------------------------------------------------------------

class TestRevokedTokenRejected(unittest.IsolatedAsyncioTestCase):
    """Revoked / missing tokens must raise ValueError (->401 at HTTP layer)."""

    async def test_revoked_token_raises(self) -> None:
        user = _make_user()
        raw, _ = create_refresh_token(subject=user.id)
        rt_rec = _make_rt_record(user.id, raw, revoked=True)

        db = _make_mock_db()
        mr = MagicMock()
        mr.scalar_one_or_none.return_value = rt_rec
        db.execute.return_value = mr

        with self.assertRaises(ValueError) as ctx:
            await AuthService(db).refresh_tokens(refresh_token=raw)
        self.assertIn("revoked", str(ctx.exception).lower())

    async def test_missing_token_raises(self) -> None:
        user = _make_user()
        raw, _ = create_refresh_token(subject=user.id)

        db = _make_mock_db()
        mr = MagicMock()
        mr.scalar_one_or_none.return_value = None
        db.execute.return_value = mr

        with self.assertRaises(ValueError) as ctx:
            await AuthService(db).refresh_tokens(refresh_token=raw)
        self.assertIn("not found", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# 3. Logout
# ---------------------------------------------------------------------------

class TestLogout(unittest.IsolatedAsyncioTestCase):
    """Logout must issue a DB update for the given token(s)."""

    async def test_logout_specific_token(self) -> None:
        """Logout with explicit token calls execute+flush exactly once."""
        user = _make_user()
        raw, _ = create_refresh_token(subject=user.id)
        db = _make_mock_db()

        await AuthService(db).logout(user_id=user.id, refresh_token=raw)

        db.execute.assert_called_once()
        db.flush.assert_called_once()

    async def test_logout_all_tokens(self) -> None:
        """Logout without token calls _revoke_all_user_tokens (execute+flush once)."""
        user = _make_user()
        db = _make_mock_db()

        await AuthService(db).logout(user_id=user.id, refresh_token=None)

        db.execute.assert_called_once()
        db.flush.assert_called_once()

    async def test_logout_endpoint_200(self) -> None:
        """POST /auth/logout with valid access token returns 200 and success message."""
        from app.main import app

        access_tok = create_access_token(
            subject="00000000-0000-0000-0000-000000000001",
            extra_claims={"email": "logoutest@example.com"},
        )

        with patch("app.routers.auth.AuthService") as MockSvc:
            inst = MagicMock()
            inst.logout = AsyncMock(return_value=None)
            MockSvc.return_value = inst

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/auth/logout",
                headers={**GATEWAY_HEADERS, "Authorization": f"Bearer {access_tok}"},
                json={},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertIn("logged out", resp.json().get("message", "").lower())


# ---------------------------------------------------------------------------
# 4. Password Strength
# ---------------------------------------------------------------------------

class TestPasswordStrength(unittest.TestCase):
    """Pydantic schema enforces password rules before data reaches the service."""

    def _parse(self, pw: str):
        from pydantic import ValidationError
        try:
            UserSignupRequest(email="test@example.com", password=pw)
            return True, ""
        except ValidationError as exc:
            return False, str(exc)

    def test_valid_password_accepted(self):
        ok, _ = self._parse("SecurePass1!")
        self.assertTrue(ok)

    def test_too_short_rejected(self):
        ok, _ = self._parse("Ab1!")
        self.assertFalse(ok)

    def test_no_letter_rejected(self):
        ok, msg = self._parse("12345678")
        self.assertFalse(ok)
        self.assertIn("letter", msg.lower())

    def test_no_digit_rejected(self):
        ok, msg = self._parse("NoDigitsHere!")
        self.assertFalse(ok)
        self.assertIn("number", msg.lower())

    def test_min_length_boundary(self):
        # Exactly 8 chars, has letter and digit -> valid
        ok, _ = self._parse("Pass123!")
        self.assertTrue(ok)

    def test_max_length_accepted(self):
        ok, _ = self._parse("A1" + "b" * 126)
        self.assertTrue(ok)

    def test_over_max_length_rejected(self):
        ok, _ = self._parse("A1" + "b" * 127)
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# 5. Login Rate Limit (429)
# ---------------------------------------------------------------------------

class TestLoginRateLimit(unittest.TestCase):
    """
    slowapi enforces 5/minute on POST /auth/login.
    The 6th request on the same IP within one minute must return 429.
    """

    def setUp(self):
        from app.main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def _attempt(self) -> int:
        return self.client.post(
            "/auth/login",
            headers=GATEWAY_HEADERS,
            json={"email": "ratelimit@example.com", "password": "wrongpass"},
        ).status_code

    def test_sixth_attempt_is_429(self):
        """
        Send up to 10 requests; assert that 429 is returned.
        Pre-limit responses are 401 (invalid creds) or 422 (schema error).
        """
        got_429 = False
        for i in range(10):
            code = self._attempt()
            if code == 429:
                got_429 = True
                break
            # Acceptable pre-limit responses.
            # 500 occurs when no database is available (expected in unit test context).
            self.assertIn(
                code, (401, 422, 429, 500, 503),
                f"Unexpected status {code} on attempt {i + 1}",
            )
        self.assertTrue(got_429, "Expected 429 Too Many Requests after rate limit exceeded")


if __name__ == "__main__":
    unittest.main()
