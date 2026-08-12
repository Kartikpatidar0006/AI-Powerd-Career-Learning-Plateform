"""Authentication dependency shim for non-auth microservices."""
from __future__ import annotations
import uuid
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from app.core.security import decode_token

_bearer_scheme = HTTPBearer(auto_error=False)

class UserClaims(BaseModel):
    id: uuid.UUID
    email: str = "user@example.com"
    is_active: bool = True
    is_verified: bool = True

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> UserClaims:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    payload = decode_token(credentials.credentials)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )
    return UserClaims(id=uuid.UUID(str(sub)))
