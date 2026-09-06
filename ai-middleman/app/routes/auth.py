"""Owner session endpoints. The password is never returned or stored in the SPA."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.security import (
    can_attempt_login, clear_login_attempts, clear_session_cookie, record_failed_login,
    require_admin, security_settings, set_session_cookie, verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


@router.post("/login", status_code=204)
async def login(body: LoginRequest, request: Request) -> Response:
    if not can_attempt_login(request):
        raise HTTPException(status_code=429, detail="Too many login attempts; try again later")
    settings = security_settings()
    if not verify_password(body.password, settings.password_hash):
        record_failed_login(request)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    clear_login_attempts(request)
    response = Response(status_code=204)
    set_session_cookie(response)
    return response


@router.post("/logout", status_code=204, dependencies=[Depends(require_admin)])
async def logout() -> Response:
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


@router.get("/session", dependencies=[Depends(require_admin)])
async def session() -> dict:
    return {"authenticated": True}
