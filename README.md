# null Community Platform

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Django](https://img.shields.io/badge/django-5.1-092e20)
![Tests](https://img.shields.io/badge/tests-210%20passing%20%C2%B7%2096%25%20coverage-brightgreen)

A Django rewrite of [swachalit](https://github.com/null-open-security-community/swachalit),
the Rails app powering [null.community](https://null.community) — India's largest
open security community. The original runs Ruby 2.6 / Rails 4.2, both long past
upstream maintenance, which makes local setup brittle and discourages
contribution from a community that mostly writes Python. This rewrite targets
**Django 5 / Python 3.12+** with the same database schema, the same URLs where
practical, and the same visual design (Bootstrap 3 + Bootswatch Yeti + Font
Awesome, vendored locally — no CDNs).

It has since moved well beyond a 1:1 port: chapter sites are **multi-tenant on
one server**, and the Rev 3 roadmap (check-in, waitlists, CFP pipeline,
analytics, trust & safety, and more) is fully implemented.

## Highlights

- **Multi-tenant chapter sites** — every chapter gets its own site (subdomain
  or custom domain) from one deployment; Caddy issues TLS on demand, gated so
  only registered chapter domains get certs.
- **Events & RSVP** — registration windows, capacity, Provisional/Confirmed
  state machine, custom RSVP questions, waitlists with auto-promotion,
  invite-only approval queues, no-show strikes, group iCal feeds.
- **Check-in** — QR tickets, scanner and kiosk modes, per-event opt-in.
- **Sessions & CFP** — proposals, review pipeline, speaker notifications,
  site-wide talk archive with search, comments, voting, Q&A, "My Sessions".
- **Chapter-leader tooling** (`/leads/`) — event/session/venue CRUD,
  registration CSV export and mass update, mailer tasks, dashboards.
- **Notifications** — seven automatic Celery-driven modes ported from the
  original, leader email blasts, a per-user preference center, feedback
  surveys, broadcast channels (Discord / Slack / Telegram / X), HMAC-signed
  outbound webhooks, Anymail/Mailgun delivery.
- **Trust & safety** — versioned Code of Conduct, incident reporting, account
  anonymization, data export, TOTP 2FA for privileged users.
- **Analytics & SEO** — cookieless per-domain analytics with chapter
  dashboards; host-scoped sitemaps, OpenGraph, JSON-LD, canonicals.
- **API v2** — DRF endpoints matching the original Grape API's contract
  (paths, field shapes, bearer-token auth), with Swagger UI at
  `/api-v2/swagger/`.
- **Auth** — django-allauth email signup with a custom email-only user model,
  env-gated Google/GitHub OAuth, reCAPTCHA.

The full catalogue, by audience, is in [`docs/FEATURES.md`](docs/FEATURES.md).

## Status

Feature-complete for the site's core member-facing and chapter-leader
workflows, backed by a 210-test pytest suite (96% coverage across `apps/`) and
CI (pytest + migration check + `manage.py check --deploy` under prod settings,
CodeQL, secret scanning). An adversarial audit of the "delivered" claim — and
the fixes it produced — is in
[`docs/rev3-delivery-audit.md`](docs/rev3-delivery-audit.md).

What is genuinely **not** exercised yet:

- **Real production boot** — `prod.py` is smoke-checked in CI, but a live
  deploy with `mysqlclient`, real SMTP/S3/reCAPTCHA keys is deployment-time
  work. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
- **Credential-gated integrations** — Mailgun, Google Calendar sync, S3 media,
  OAuth logins, Sentry, and broadcast channels are built but need keys; all
  degrade gracefully without them (see
  [`docs/ROADMAP.md`](docs/ROADMAP.md#credential-gated-integrations-built-need-keys)).
- **Scheduled notification sweeps** — dev runs Celery eagerly, so on-demand
  mail works but time-based reminders need `celery -A config beat` + a worker
  (as in a real deployment). By design, not a bug.

Intentionally dropped from the original: IFTTT/Twitter posting (dead upstream —
replaced by the broadcast channels), the Slack inbound bot, and the legacy
pre-Grape `/api/*` v1 endpoints.

## Quickstart

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

docker compose up -d        # MySQL on :3307, Redis on :6380
cp .env.example .env        # defaults match docker-compose.yml

python manage.py migrate
python manage.py createsuperuser
python manage.py shell < scripts/seed_dev_data.py   # optional seed data
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` — admin at `/admin/`. Chapter sites need no DNS
tricks in dev: browsers resolve `*.localhost` to 127.0.0.1, so
`http://delhi.localhost:8000` works as soon as a chapter named "Delhi" exists.

> **Why PyMySQL?** `mysqlclient` needs `libmysqlclient-dev` on the host, which
> many dev machines lack. `config/__init__.py` shims
> `pymysql.install_as_MySQLdb()` so the same Django MySQL backend works with
> either driver; the production Dockerfile installs the real thing.

### Running the tests

```bash
pytest                                        # 210 tests, ~2s
pytest --cov=apps --cov-report=term-missing   # with coverage breakdown
```

pytest-django creates a real `test_swachalit` MySQL database (`--reuse-db` is
on; pass `--create-db` for a clean slate). On Python 3.14, install
`pytest pytest-django pytest-cov factory-boy faker` directly instead of
`requirements-dev.txt` — the pinned `safety` doesn't build there yet. More in
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## Chapter sites (multi-tenant, one server)

A chapter "site" is just data: the `Chapter` row (auto-filled `subdomain`,
optional `custom_domain`) plus its events and pages. How a request finds its
chapter:

1. **DNS** — a wildcard `*.example.com` record points at the one server;
   custom domains CNAME to the same place.
2. **TLS** — Caddy (`deploy/Caddyfile`) holds one wildcard cert and issues
   per-domain certs on demand, gated by `GET /domains/check?domain=`, which
   only approves domains registered to an active chapter.
3. **Django** — `ChapterSiteMiddleware` reads the Host header and sets
   `request.chapter` (`None` on the root domain = the directory site; unknown
   hosts 404). Home, archives, and sessions scope to the current chapter.

Set `ROOT_DOMAIN` plus, in prod, `SESSION_COOKIE_DOMAIN` / `CSRF_COOKIE_DOMAIN`
so one login spans every chapter subdomain. Details in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Architecture

```
apps/
  accounts/      User, auth profiles, API tokens, 2FA
  chapters/      Chapter, ChapterLead, directory + pin map
  events/        events, sessions, registrations, venues, voting, check-in
  content/       CMS pages + per-page edit permissions
  proposals/     CFP: session proposals/requests, achievements
  leads/         chapter-leader namespace (CRUD, CSV export, mailer tasks)
  notifications/ mailer + automatic-notification Celery tasks, broadcasts
  analytics/     cookieless per-domain analytics, chapter dashboards
  api/           DRF token auth, /api-v2/ endpoints, Swagger schema
  core/          home/stats views, context processors, template tags
config/settings/ base.py → dev.py / prod.py / showcase.py
templates/       ported from the original ERB views
static/vendor/   locally-hosted Bootstrap 3 + Bootswatch Yeti + FA4
```

Every model file's docstring points back to the Rails model it was ported from
(e.g. "See app/models/event.rb").

## Documentation

Full docs live in [`docs/`](docs/README.md):
[architecture](docs/ARCHITECTURE.md) · [features](docs/FEATURES.md) ·
[data model](docs/DATA_MODEL.md) · [development](docs/DEVELOPMENT.md) ·
[deployment](docs/DEPLOYMENT.md) · [upgrading](docs/UPGRADING.md) ·
[roadmap](docs/ROADMAP.md)

## Contributing & security

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose changes and
[SECURITY.md](SECURITY.md) for reporting vulnerabilities. Deferred features
and improvement ideas are tracked in [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

*Made with [Claude Code](https://claude.com/claude-code).*
