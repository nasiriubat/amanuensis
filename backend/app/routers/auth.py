from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import current_user, get_session
from ..models import AuthSession, User
from ..schemas import ChangePasswordIn, LoginIn, UpdateMeIn, UserOut
from ..security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    hash_password,
    login_limiter,
    new_token,
    session_expiry,
    token_id,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookies(response: Response, token: str, csrf: str) -> None:
    settings = get_settings()
    max_age = settings.session_ttl_hours * 3600
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        path="/",
    )
    # Readable by JS on purpose: double-submit CSRF pattern.
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        httponly=False,
        samesite="lax",
        secure=settings.secure_cookies,
        path="/",
    )


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    client = request.client.host if request.client else "unknown"
    if not login_limiter.allow(f"{client}:{body.email.lower()}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try again in a few minutes.")
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    token = new_token()
    csrf = new_token(24)
    sess = AuthSession(
        id=token_id(token),
        user_id=user.id,
        csrf_token=csrf,
        expires_at=session_expiry(),
        user_agent=(request.headers.get("user-agent") or "")[:255],
    )
    db.add(sess)
    db.commit()
    _set_cookies(response, token, csrf)
    return user


@router.post("/logout", status_code=204)
def logout(response: Response, sess: AuthSession | None = Depends(get_session), db: Session = Depends(get_db)):
    if sess:
        db.delete(sess)
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UpdateMeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.display_name = body.display_name
    db.commit()
    return user


@router.post("/change-password", response_model=UserOut)
def change_password(body: ChangePasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is wrong")
    if body.current_password == body.new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must differ from the current one")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    db.commit()
    return user
