"""Auth router. Only one endpoint: verify the shared password."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth.middleware import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class VerifyIn(BaseModel):
    password: str


class VerifyOut(BaseModel):
    ok: bool
    token: str


@router.post("/verify", response_model=VerifyOut)
async def verify(body: VerifyIn) -> VerifyOut:
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    # Token == password (single shared-key model).  The UI stores it and sends it as X-Access-Token.
    return VerifyOut(ok=True, token=body.password)
