# Security

## Reporting a vulnerability

Please report security problems privately through GitHub's "Report a vulnerability" button on the
Security tab of this repository. Do not open a public issue. You will get an acknowledgement within
a week and a fix or a plan within a month for anything that affects a default installation.

## What the application protects

Coscribe is a self-hosted web application meant to run for one research group behind HTTPS.

- Passwords are hashed with argon2. Sessions are HttpOnly cookies stored by hash; CSRF uses a
  double-submit token.
- Provider API keys and the SMTP password are encrypted at rest with a key derived from
  `APP_SECRET_KEY`. Losing that key means re-entering them.
- Uploads are checked by their bytes, not their extension. SVGs are sanitised. User files are
  served with a sandboxing content-security policy and never executed.
- Requests over 45 MB are rejected before they are read. Rate limits apply to sign-in and to
  endpoints that call a model.
- Prompts leave the server only to the model provider the administrator configured.

## What it does not do

- It is a single process with SQLite. It is not designed for the public internet or for untrusted
  users sharing one instance; members are invited by an administrator.
- It does not sandbox LaTeX. Export runs Tectonic on Markdown the members wrote; do not give
  accounts to people you would not let run LaTeX on your server.
- It stores the papers people write. Treat the data volume as confidential and back it up.

## Supported versions

The `main` branch and the latest tagged release.
