from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuthSession, User, now
from .security import CSRF_HEADER, SESSION_COOKIE, token_id

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_session(request: Request, db: Session = Depends(get_db)) -> AuthSession | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    sess = db.get(AuthSession, token_id(token))
    if not sess:
        return None
    if sess.expires_at.replace(tzinfo=None) < now().replace(tzinfo=None):
        db.delete(sess)
        db.commit()
        return None
    return sess


def current_user(
    request: Request,
    sess: AuthSession | None = Depends(get_session),
) -> User:
    if sess is None or not sess.user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    if request.method not in SAFE_METHODS:
        header = request.headers.get(CSRF_HEADER)
        if not header or header != sess.csrf_token:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF check failed")
    return sess.user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user
