"""Outgoing email (ROADMAP item 8): invitations and password resets over SMTP.

Settings live in the `site_settings` row "mail"; the password is encrypted with the app's
Fernet key like provider keys. When mail is not configured everything falls back to the
on-screen behaviour (the admin reads out a temporary password), so nothing here is required.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy.orm import Session

from .config import get_settings
from .models import SiteSetting
from .security import decrypt_secret, encrypt_secret, key_hint

MAIL_DEFAULTS = {
    "enabled": False,
    "host": "",
    "port": 587,
    "security": "starttls",  # starttls | ssl | none
    "username": "",
    "password_enc": "",
    "from_addr": "",
    "from_name": "",
}

TIMEOUT_S = 15


class MailError(RuntimeError):
    pass


def load_mail(db: Session) -> dict:
    row = db.get(SiteSetting, "mail")
    data = dict(MAIL_DEFAULTS)
    if row and row.value:
        data.update(row.value)
    return data


def save_mail(db: Session, data: dict) -> dict:
    row = db.get(SiteSetting, "mail")
    if not row:
        row = SiteSetting(key="mail", value=data)
        db.add(row)
    else:
        row.value = data
    db.commit()
    return data


def public_view(data: dict) -> dict:
    """What the admin UI sees: never the password itself."""
    out = {k: v for k, v in data.items() if k != "password_enc"}
    out["has_password"] = bool(data.get("password_enc"))
    out["password_hint"] = key_hint(decrypt_secret(data["password_enc"])) if data.get("password_enc") else None
    return out


def configured(data: dict) -> bool:
    return bool(data.get("enabled") and data.get("host") and data.get("from_addr"))


def is_configured(db: Session) -> bool:
    return configured(load_mail(db))


def update(db: Session, patch: dict, password: str | None) -> dict:
    data = {**load_mail(db), **patch}
    if password is not None:
        data["password_enc"] = encrypt_secret(password) if password else ""
    return save_mail(db, data)


def _connect(data: dict) -> smtplib.SMTP:
    host, port = data["host"], int(data.get("port") or 587)
    if data.get("security") == "ssl":
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT_S, context=ssl.create_default_context())
    else:
        smtp = smtplib.SMTP(host, port, timeout=TIMEOUT_S)
        smtp.ehlo()
        if data.get("security", "starttls") == "starttls":
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
    if data.get("username"):
        smtp.login(data["username"], decrypt_secret(data["password_enc"]) if data.get("password_enc") else "")
    return smtp


def send(db: Session, to: str, subject: str, body: str) -> None:
    """Send one plain-text message. Raises MailError with a sentence the admin can act on."""
    data = load_mail(db)
    if not configured(data):
        raise MailError("Email is not configured. Add an SMTP server under Settings → Site.")
    msg = EmailMessage()
    msg["From"] = (
        formataddr((data.get("from_name") or "", data["from_addr"])) if data.get("from_name") else data["from_addr"]
    )
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with _connect(data) as smtp:
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise MailError("The SMTP server rejected the username or password.") from e
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"Could not reach the SMTP server: {str(e)[:120]}") from e


# ------------------------------------------------------------------ messages


def _site_name(db: Session) -> str:
    row = db.get(SiteSetting, "site")
    return (row.value or {}).get("name", "Paper Writer") if row else "Paper Writer"


def invitation(db: Session, *, display_name: str, email: str, password: str, invited_by: str) -> tuple[str, str]:
    name = _site_name(db)
    url = get_settings().app_url.rstrip("/")
    subject = f"{invited_by} invited you to {name}"
    body = (
        f"Hello {display_name},\n\n"
        f"{invited_by} created an account for you on {name}, a tool for writing research papers "
        f"from what you built or plan to study.\n\n"
        f"Sign in here: {url}/login\n"
        f"Email: {email}\n"
        f"Temporary password: {password}\n\n"
        f"You will be asked to choose your own password on first sign-in.\n"
    )
    return subject, body


def new_password(db: Session, *, display_name: str, password: str) -> tuple[str, str]:
    name = _site_name(db)
    url = get_settings().app_url.rstrip("/")
    subject = f"Your {name} password was reset"
    body = (
        f"Hello {display_name},\n\n"
        f"An administrator reset your password on {name}.\n\n"
        f"Sign in here: {url}/login\n"
        f"Temporary password: {password}\n\n"
        f"You will be asked to choose your own password on first sign-in.\n"
    )
    return subject, body


def reset_link(db: Session, *, display_name: str, token: str) -> tuple[str, str]:
    name = _site_name(db)
    url = get_settings().app_url.rstrip("/")
    subject = f"Reset your {name} password"
    body = (
        f"Hello {display_name},\n\n"
        f"Someone asked to reset the password for this address on {name}. If it was you, open this "
        f"link within one hour:\n\n{url}/reset-password?token={token}\n\n"
        f"If it was not you, ignore this message. Your password stays as it is.\n"
    )
    return subject, body
