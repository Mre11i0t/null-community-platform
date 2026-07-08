# Deployment

This project ships two deployment paths from the same codebase:

| Path | Settings module | TLS | Use |
|---|---|---|---|
| **Production** (intended) | `config.settings.prod` | Caddy wildcard cert (ACME DNS-01) at the origin | Real multi-tenant hosting on `ROOT_DOMAIN` + `*.ROOT_DOMAIN` |
| **Showcase** (Mac Mini) | `config.settings.showcase` | Cloudflare Tunnel — TLS terminates at Cloudflare's edge, plain HTTP to a local gunicorn | Throwaway next-day demo |

Both inherit `config/settings/base.py`. `showcase.py` inherits `prod.py` and relaxes a handful of settings for a demo host. The 202-test suite runs under `config.settings.test`.

The chapter-sites architecture serves the root/directory site at the bare `ROOT_DOMAIN` and every chapter as a subdomain (`delhi.<ROOT_DOMAIN>`), routed by `apps.chapters.middleware.ChapterSiteMiddleware`. A single login works across all subdomains via a shared cookie domain.

---

## Path 1 — Production

Files: `config/settings/prod.py`, `Dockerfile`, `deploy/Caddyfile`, `docker-compose.yml`.

### What `prod.py` enforces

- `DEBUG = False`.
- `SECURE_SSL_REDIRECT = True`, `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE = True`.
- HSTS: `SECURE_HSTS_SECONDS = 31536000`, include-subdomains + preload on; `SECURE_CONTENT_TYPE_NOSNIFF = True`.
- `ALLOWED_HOSTS` (env, default `["null.community"]`).
- `CSRF_TRUSTED_ORIGINS` (env; default `https://{ROOT_DOMAIN}` and `https://*.{ROOT_DOMAIN}` — the wildcard covers every chapter subdomain).
- `REQUIRE_2FA_FOR_PRIVILEGED = True` (chapter leads need TOTP for `/leads/`, staff for `/admin/`).
- Static and media storage — see [Static & media](#static--media-behavior).

### Container

`Dockerfile` builds on `python:3.12-slim`, installs `default-libmysqlclient-dev` (real `mysqlclient`), installs `requirements.txt`, and runs:

```
gunicorn config.wsgi:application --bind 0.0.0.0:8800
```

The container EXPOSEs `8800`. Note the `deploy/Caddyfile` example reverse-proxies to `app:8000` — align the gunicorn bind port and the Caddy upstream to the same value when wiring them together.

### Reverse proxy / TLS — `deploy/Caddyfile`

One Caddy fronts one Django app and serves three classes of host:

| Host pattern | Certificate |
|---|---|
| `ROOT_DOMAIN` + `*.ROOT_DOMAIN` (root site + all chapter subdomains) | One wildcard cert via ACME **DNS challenge** (Cloudflare DNS module) |
| Chapter **custom domains** (e.g. `nulldelhi.in`) | Per-domain cert, issued **on demand** on first request |

On-demand issuance is gated: before minting a cert for an unknown host, Caddy calls `http://app:8000/domains/check` (the `on_demand_tls ask` directive) so only domains belonging to an active chapter get certificates. The wildcard cert requires a Caddy built with the DNS provider module:

```
xcaddy build --with github.com/caddy-dns/cloudflare
```

The Caddyfile reads `CLOUDFLARE_API_TOKEN` from the environment for the DNS challenge. Replace `null.community`/`admin@null.community` with your own domain and ACME contact.

### Data services

`docker-compose.yml` provides `db` (MySQL 8.0) and `redis` (Redis 7), both bound to loopback only on the host (`127.0.0.1:3307` → 3306, `127.0.0.1:6380` → 6379). MySQL data persists in the `ncp-mysql` volume.

---

## Path 2 — Showcase (Mac Mini + Cloudflare Tunnel)

Files: `deploy/showcase/README.md`, `deploy/showcase/env.showcase.example`, `scripts/run_showcase.sh`, `scripts/showcase_screen.sh`, `config/settings/showcase.py`.

Request path:

```
browser --https--> Cloudflare edge --tunnel--> cloudflared --http--> gunicorn 127.0.0.1:8000
```

Cloudflare terminates TLS at its edge, so there is **no Caddy and no certificates to manage**. The free Cloudflare Universal SSL wildcard covers the apex plus **one** subdomain level, so the demo scheme keeps chapters one level under the apex (`delhi.<domain>`, not nested).

### What `showcase.py` changes vs. prod

| Setting | Value | Reason |
|---|---|---|
| `SECURE_PROXY_SSL_HEADER` | trusts `X-Forwarded-Proto` | edge is HTTPS, origin gets HTTP |
| `SECURE_SSL_REDIRECT` | `False` | edge already forces HTTPS (avoids a redirect loop) |
| `SECURE_HSTS_SECONDS` | `0` (preload/subdomains off) | never pin HSTS onto a real domain for a throwaway demo |
| `SESSION_COOKIE_DOMAIN` / `CSRF_COOKIE_DOMAIN` | env, e.g. `.example.com` | one login across every chapter subdomain |
| `CELERY_TASK_ALWAYS_EAGER` | `True` | run tasks inline — no separate worker/beat (time-based reminders won't fire) |
| `EMAIL_BACKEND` | console (unless a Mailgun key is set) | mail prints to the gunicorn log |
| `ACCOUNT_EMAIL_VERIFICATION` | `optional` | seeded demo users have no real inbox |
| `RECAPTCHA_*` | Google published **test** keys (unless overridden) | signup/RSVP/comment forms work out of the box |
| `REQUIRE_2FA_FOR_PRIVILEGED` | `False` (default) | frictionless demo |

### Bring-up

1. **One-time Cloudflare Tunnel setup** (`deploy/showcase/README.md` Part 1): `cloudflared tunnel login`, `tunnel create null-showcase`, write `~/.cloudflared/config.yml` listing the apex + named chapter hostnames explicitly (no wildcard ingress), then `cloudflared tunnel route dns` for each hostname. Set SSL/TLS mode to **Full** and enable **Always Use HTTPS** in the dashboard.
2. **Configure env**: `cp deploy/showcase/env.showcase.example deploy/showcase/.env.showcase` and fill it in (a long random `DJANGO_SECRET_KEY`, `ROOT_DOMAIN`, `SITE_BASE_URL`, the `*_COOKIE_DOMAIN` vars). Load with `set -a; source deploy/showcase/.env.showcase; set +a`.
3. **Run the app**: `./scripts/run_showcase.sh` — brings up `db` + `redis` via docker compose, waits for MySQL, runs `migrate`, `collectstatic`, seeds demo data (`scripts/seed_rev3_data.py`), then execs `gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3`.
4. **Run the tunnel** in a second terminal: `cloudflared tunnel run null-showcase`.

`DJANGO_SETTINGS_MODULE=config.settings.showcase` is exported by both `run_showcase.sh` and `env.showcase.example`.

### Detached / survives-disconnect

`scripts/showcase_screen.sh` starts gunicorn (session `null-app`) and cloudflared (session `null-tunnel`) in two detached `screen` sessions, clears any prior processes first, and does a local health check (`curl` with a spoofed `Host:` header). Reattach with `screen -r null-app` / `screen -r null-tunnel`. For reboot survival, install the tunnel as a service (`sudo cloudflared service install`).

macOS note: install `gunicorn` alone, not the full `requirements.txt` — the venv uses a PyMySQL shim to avoid building `mysqlclient`.

---

## Environment variables

Read from `config/settings/base.py` (unless noted), via `django-environ`. **Names only — never commit values. Rotate any secret that has been shared in plaintext.**

### Core / hosting

| Variable | Notes |
|---|---|
| `DJANGO_SECRET_KEY` | Required in prod/showcase; scripts abort if unset |
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` or `config.settings.showcase` |
| `ROOT_DOMAIN` | Hostname only (no scheme/port); its subdomains are chapter sites |
| `SITE_BASE_URL` | Absolute base for URLs built in emails |
| `ALLOWED_HOSTS` | *prod.py* — list |
| `SESSION_COOKIE_DOMAIN`, `CSRF_COOKIE_DOMAIN` | Set to `.<ROOT_DOMAIN>` (leading dot) for cross-subdomain login |
| `CSRF_TRUSTED_ORIGINS` | *prod.py* — defaults to `https://{ROOT_DOMAIN}` + wildcard |

### Database & Redis

| Variable | Notes |
|---|---|
| `MYSQL_DATABASE`, `MYSQL_USERNAME`, `MYSQL_PASSWORD`, `MYSQL_SERVER`, `MYSQL_PORT` | MySQL connection (charset `utf8mb4`) |
| `REDIS_URL` | Celery broker (`CELERY_RESULT_BACKEND` is `django-db`) |

### Email — Mailgun (via django-anymail) with SMTP fallback

| Variable | Notes |
|---|---|
| `MAILGUN_API_KEY` **or** `MAILGUN_SENDING_KEY` | Presence switches `EMAIL_BACKEND` to anymail Mailgun |
| `MAILGUN_SENDER_DOMAIN`, `MAILGUN_API_URL` | anymail config |
| `MAILGUN_SMTP_HOST`, `MAILGUN_SMTP_PORT`, `MAILGUN_SMTP_USER`, `MAILGUN_SMTP_PASSWORD` | SMTP fallback used only when no Mailgun key is set |
| `DEFAULT_FROM_EMAIL` | From address |

### Social login (OAuth, env-gated — provider app only installs when set)

| Variable | Notes |
|---|---|
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Google allauth provider |
| `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET` | GitHub allauth provider |

### Maps, CAPTCHA, monitoring

| Variable | Notes |
|---|---|
| `GOOGLE_MAPS_API_KEY` | Root-directory pin map; without it, directory falls back to a plain grid. Also extends the CSP `script-src` |
| `RECAPTCHA_PUBLIC_KEY`, `RECAPTCHA_PRIVATE_KEY` | Signup / RSVP / comment forms |
| `SENTRY_DSN` | Env-gated; enables `sentry_sdk` (traces 0.1, no PII) |

### Media storage (S3, env-gated in prod.py)

| Variable | Notes |
|---|---|
| `AWS_STORAGE_BUCKET_NAME` | When set, media goes to S3; else local disk |
| `AWS_S3_REGION_NAME` | Defaults to `ap-south-1` |

### Broadcast channels & X/Twitter (all env-gated)

| Variable | Notes |
|---|---|
| `DISCORD_WEBHOOK_URL`, `SLACK_WEBHOOK_URL` | Webhook channels |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram |
| `X_CONSUMER_KEY`, `X_CONSUMER_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET` | X API v2 (optional, pay-per-use) |
| `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp |

### Reverse proxy (Caddyfile)

| Variable | Notes |
|---|---|
| `CLOUDFLARE_API_TOKEN` | Read by Caddy for the ACME DNS challenge (wildcard cert) |

### Behavior / policy tunables (non-secret)

`REQUIRE_2FA_FOR_PRIVILEGED`, `NO_SHOW_STRIKE_LIMIT`, `NO_SHOW_WINDOW_DAYS`, `COC_VERSION`, `INCIDENT_RESPONSE_ADDRESSES`, `FEEDBACK_DELAY_HOURS`, `NOTIFICATION_ANNOUNCEMENT_ADDRESSES`, `NOTIFICATION_ADMIN_EVENT_CREATE`, `CFG_APP_TITLE`, `CFG_APP_DESCRIPTION`, `CFG_VOLUNTEER_FORM_URL`.

---

## Static & media behavior

**Static (WhiteNoise).** `prod.py` sets the `staticfiles` storage to `whitenoise.storage.CompressedStaticFilesStorage` (gzip/brotli). It deliberately uses the **non-manifest** variant: vendored Bootstrap/Bootswatch CSS carries a few dangling asset references, and the manifest backend would turn each into a hard `collectstatic` failure. Trade-off: no hashed-filename cache-busting. `WhiteNoiseMiddleware` sits directly after `SecurityMiddleware`. Run `collectstatic` on deploy (`run_showcase.sh` does this).

**Media (S3 or local).** `prod.py` sets the `default` storage to `S3Boto3Storage` when `AWS_STORAGE_BUCKET_NAME` is set, otherwise `FileSystemStorage`. For the local-disk case (DEBUG off), `config/urls.py` explicitly serves `^media/` via `django.views.static.serve`, since the `static()` helper is a no-op when `DEBUG=False`. Fine for a small/showcase host; use S3 or a front-proxy file server for real traffic. The showcase serves media off local disk by default.

---

## Content Security Policy

Set in `base.py` via `django-csp`. The pinned version is **3.8**, which reads the **flat `CSP_*`** settings (the `CONTENT_SECURITY_POLICY` dict is 4.x syntax and is kept in sync only for a future upgrade). Applied by `csp.middleware.CSPMiddleware`.

| Directive | Sources |
|---|---|
| `default-src` | `'self'` |
| `script-src` | `'self'`, Razorpay checkout, Google/gstatic reCAPTCHA, jsDelivr (Swagger UI), `'unsafe-inline'`; **+ Google Maps** (`maps.googleapis.com`, `maps.gstatic.com`) only when `GOOGLE_MAPS_API_KEY` is set |
| `style-src` | `'self'`, `'unsafe-inline'`, Google Fonts, jsDelivr |
| `font-src` | `'self'`, gstatic fonts, `data:` |
| `img-src` | `'self'`, `data:`, `https:` |
| `frame-src` | `'self'`, Google reCAPTCHA |
| `connect-src` | `'self'`, `maps.googleapis.com` |

---

## Security posture caveats

The showcase is a **demo** posture, not a hardened production deploy: single host, seeded demo data, HSTS disabled, 2FA off, reCAPTCHA on public test keys, `ACCOUNT_EMAIL_VERIFICATION = optional`, and Celery run inline (no time-based reminders). Do not leave it exposed long-term as-is; for real traffic use `config.settings.prod` with genuine reCAPTCHA/2FA, S3 media, a running Celery worker + beat, and real Mailgun credentials.

---

### Referenced files

- `config/settings/base.py`, `config/settings/prod.py`, `config/settings/showcase.py`
- `config/urls.py` (media serving)
- `Dockerfile`, `docker-compose.yml`, `deploy/Caddyfile`
- `deploy/showcase/README.md`, `deploy/showcase/env.showcase.example`
- `scripts/run_showcase.sh`, `scripts/showcase_screen.sh`, `scripts/seed_rev3_data.py`

---

*Made with [Claude Code](https://claude.com/claude-code).*
