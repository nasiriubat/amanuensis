"""Email: settings, invitations, password resets. SMTP is faked in-process."""

from typing import ClassVar

from conftest import login

from app import mail

MAIL_CFG = {
    "enabled": True,
    "host": "smtp.test",
    "port": 587,
    "username": "bot",
    "password": "s3cret-pass",
    "from_addr": "pw@test.local",
    "from_name": "Amanuensis",
}
KEEP = ("enabled", "host", "port", "security", "username", "from_addr", "from_name")


class FakeSMTP:
    sent: ClassVar[list[dict]] = []
    fail_auth: ClassVar[bool] = False

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port = host, port
        self.logged_in = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        pass

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        import smtplib

        if FakeSMTP.fail_auth:
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
        self.logged_in = (user, password)

    def send_message(self, msg):
        FakeSMTP.sent.append(
            {"to": msg["To"], "subject": msg["Subject"], "body": msg.get_content(), "login": self.logged_in}
        )


def _configure(client, admin, monkeypatch):
    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent.clear()
    FakeSMTP.fail_auth = False
    r = client.put(
        "/api/admin/mail",
        json={
            "enabled": True,
            "host": "smtp.test",
            "port": 587,
            "username": "bot",
            "password": "s3cret-pass",
            "from_addr": "pw@test.local",
            "from_name": "Amanuensis",
        },
        headers=admin,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_mail_settings_hide_password_and_validate(client, admin, monkeypatch):
    view = _configure(client, admin, monkeypatch)
    assert (
        view["has_password"]
        and view["password_hint"] == "pass"
        and "password_enc" not in view
        and "password" not in view
    )
    # saving again without a password keeps the stored one
    r = client.put(
        "/api/admin/mail",
        json={**{k: view[k] for k in ("enabled", "host", "port", "security", "username", "from_addr", "from_name")}},
        headers=admin,
    )
    assert r.json()["has_password"]
    bad = client.put("/api/admin/mail", json={"enabled": True, "host": "", "from_addr": ""}, headers=admin)
    assert bad.status_code == 400
    assert client.get("/api/site").json()["password_reset"] is True
    t = client.post("/api/admin/mail/test", headers=admin)
    assert t.status_code == 200 and FakeSMTP.sent[-1]["to"] == "admin@test.local"
    assert FakeSMTP.sent[-1]["login"] == ("bot", "s3cret-pass")
    FakeSMTP.fail_auth = True
    t = client.post("/api/admin/mail/test", headers=admin)
    assert t.status_code == 400 and "username or password" in t.json()["detail"]


def test_invitation_is_emailed_and_survives_mail_failure(client, admin, monkeypatch):
    _configure(client, admin, monkeypatch)
    r = client.post(
        "/api/users",
        json={"email": "carol@test.local", "display_name": "Carol", "password": "temp-pass-123", "send_email": True},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    assert r.json()["emailed"] is True and r.json()["email_error"] is None
    m = FakeSMTP.sent[-1]
    assert (
        m["to"] == "carol@test.local"
        and "temp-pass-123" in m["body"]
        and "/login" in m["body"]
        and "Admin" in m["subject"]
    )
    # mail broken: account still created, error reported
    FakeSMTP.fail_auth = True
    r = client.post(
        "/api/users",
        json={"email": "dave@test.local", "display_name": "Dave", "password": "temp-pass-456", "send_email": True},
        headers=admin,
    )
    assert r.status_code == 201 and r.json()["emailed"] is False and "username or password" in r.json()["email_error"]
    FakeSMTP.fail_auth = False
    # admin reset with email
    uid = r.json()["id"]
    r = client.patch(f"/api/users/{uid}", json={"password": "another-pass-9", "send_email": True}, headers=admin)
    assert r.json()["emailed"] is True and "another-pass-9" in FakeSMTP.sent[-1]["body"]
    for u in client.get("/api/users", headers=admin).json():
        if u["email"] in ("carol@test.local", "dave@test.local"):
            client.delete(f"/api/users/{u['id']}", headers=admin)


def test_forgot_and_reset_flow(client, admin, monkeypatch):
    _configure(client, admin, monkeypatch)
    client.post(
        "/api/users",
        json={"email": "erin@test.local", "display_name": "Erin", "password": "first-pass-12"},
        headers=admin,
    )
    from app.security import login_limiter

    login_limiter._hits.clear()
    # unknown address: same answer, no mail
    n = len(FakeSMTP.sent)
    assert client.post("/api/auth/forgot", json={"email": "nobody@test.local"}).status_code == 202
    assert len(FakeSMTP.sent) == n
    assert client.post("/api/auth/forgot", json={"email": "erin@test.local"}).status_code == 202
    body = FakeSMTP.sent[-1]["body"]
    token = body.split("token=", 1)[1].split()[0]
    bad = client.post("/api/auth/reset", json={"token": "x" * 40, "new_password": "whatever-123"})
    assert bad.status_code == 400
    ok = client.post("/api/auth/reset", json={"token": token, "new_password": "brand-new-pass-1"})
    assert ok.status_code == 200 and ok.json()["must_change_password"] is False
    # token is single use
    assert client.post("/api/auth/reset", json={"token": token, "new_password": "brand-new-pass-2"}).status_code == 400
    login_limiter._hits.clear()
    headers = login(client, "erin@test.local", "brand-new-pass-1")
    assert headers["x-csrf-token"]
    # back to admin for cleanup
    admin = login(client)
    for u in client.get("/api/users", headers=admin).json():
        if u["email"] == "erin@test.local":
            client.delete(f"/api/users/{u['id']}", headers=admin)
    # switch mail off: forgot explains itself
    client.put("/api/admin/mail", json={"enabled": False}, headers=admin)
    assert client.get("/api/site").json()["password_reset"] is False
    login_limiter._hits.clear()
    r = client.post("/api/auth/forgot", json={"email": "admin@test.local"})
    assert r.status_code == 400 and "not set up" in r.json()["detail"]
