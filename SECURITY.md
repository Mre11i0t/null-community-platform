# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities **privately** — do not open a public
issue. Email the maintainers (see the About page of a running deployment, which
renders a `security@<your-host>` address) or use GitHub's private
**Security advisories** ("Report a vulnerability") on this repository.

Include: affected version/commit, reproduction steps, impact, and any PoC. We
aim to acknowledge within a few days.

## Supported versions

This project tracks `main`. Security fixes land on `main`; there are no
long-term support branches. Deploy from a recent commit.

## Security posture (built in)

- **CSP** — a Content-Security-Policy is enforced (see `config/settings/base.py`);
  it whitelists only the third parties actually used (reCAPTCHA, Google Maps,
  Swagger CDN).
- **2FA** — TOTP second factor can be required for privileged accounts
  (admins + chapter leads) via `REQUIRE_2FA_FOR_PRIVILEGED`.
- **Secure cookies / HSTS / SSL redirect** in `config/settings/prod.py`.
- **CSRF** — `CSRF_TRUSTED_ORIGINS` covers the wildcard subdomain set.
- **Audit log** — `django-auditlog` records changes on 13 models.
- **On-demand-TLS gate** — `/domains/check` prevents strangers minting certs.
- **Secrets** — never committed; kept in gitignored `.env` files. CI runs a
  secret scan (`.github/workflows/secrets-scan.yml`) and CodeQL.

## Handling secrets

All credentials (DB, Mailgun, OAuth, reCAPTCHA, Maps, AWS) are read from the
environment with safe fallbacks. The only credential in the tracked tree is the
throwaway **local-docker** MySQL password (`s0m3p4ssw0rd`), which protects
nothing beyond a local container. Rotate any real key that is ever exposed.

---

*Made with [Claude Code](https://claude.com/claude-code).*
