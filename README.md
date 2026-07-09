# null Community Platform (Django)

A Django port of [swachalit](https://github.com/null-open-security-community/swachalit),
the Rails app powering [null.community](https://null.community). The
original app runs Ruby 2.6 / Rails 4.2 — both long past upstream
maintenance — which makes local setup brittle (broken on ARM64,
abandoned gems) and discourages contribution from a community that
mostly writes Python. This rewrite targets Django 5 / Python 3.12+
with the same database schema, the same URLs/routes where practical,
and the same visual design (Bootstrap 3 + Bootswatch Yeti + Font
Awesome — assets copied verbatim from the original app's
`app/assets/`).

## Status

**Rev 3 (2026-07):** the platform has moved well beyond the 1:1 Rails
port. Chapter sites are multi-tenant on one server (subdomain routing +
Caddy on-demand TLS), and the adopted Rev 3 roadmap is fully
implemented — check-in (QR/scanner/kiosk, per-event opt-in), waitlists
with auto-promotion, invite-only approval queue, custom RSVP questions,
no-show strikes, the CFP review pipeline, versioned CoC + incident
reporting + account anonymization + data export + TOTP 2FA for
privileged users, cookieless per-domain analytics with chapter
dashboards, host-scoped SEO (sitemaps/OG/JSON-LD/canonicals), the root
directory site, gamification + event discussion + galleries + session
Q&A, notification preference center + feedback surveys + WhatsApp
adapter, personal agendas, env-gated Google/GitHub login, HMAC-signed
outbound webhooks, Anymail/Mailgun delivery, and broadcast channels
(Discord/Slack/Telegram/X) replacing the dead IFTTT tweets. All ten
gaps documented in the original feature doc are closed. 189 tests.

Feature-complete for the site's core member-facing and chapter-leader
workflows. Read this section before assuming something works — a few
things are genuinely stubbed, and everything here has only been run
against **dev** settings (PyMySQL, `DEBUG=True`, reCAPTCHA test keys,
`CELERY_TASK_ALWAYS_EAGER=True`); the production path (`prod.py`,
`mysqlclient`, `collectstatic`, real email/SMTP, real reCAPTCHA keys)
has not been exercised.

A 189-test pytest suite (96% coverage across `apps/`, one `tests.py`
per app plus `apps/core/test_templatetags.py`) now backs most of what's
listed below — see "Running the tests" further down. It's what turned
up the two real bugs described in the notes under each area, and it's
what "people can actually test it" (the reason this rewrite happened)
concretely means in practice.

### Working end-to-end (verified with real seeded data driven through the actual code path — not just a 200 at the route level)

- Full data model for every table in the original `db/schema.rb`,
  Django admin registered for all of them (list filters, batch
  actions, autocomplete FK pickers).
- **Public pages**: homepage, upcoming/archived events, chapter
  directory + detail, event detail, session detail, public profile,
  CMS pages — templates ported line-by-line from the original ERB
  views, Bootstrap 3 + Bootswatch Yeti + Font Awesome 4 theme vendored
  locally under `static/vendor/` (not CDN-loaded — see below).
- **Auth**: django-allauth signup/login/logout/email-confirmation
  against the custom email-only `User` model, custom Bootstrap-themed
  templates, reCAPTCHA on signup.
- **RSVP**: registration create/cancel, Provisional/Confirmed state
  machine and registration-window/capacity validation ported from the
  original model callbacks, reCAPTCHA on the form. The pytest suite
  found a real crash here: rejecting a full or registration-closed
  event 500'd instead of showing the "all seats are gone" message,
  because the model's `ValidationError` was keyed to `"event"`, a
  field `EventRegistrationForm` doesn't expose — fixed by raising it
  as a non-field error (see `apps/events/models.py` `clean()`).
- **Session comments & voting**: full CRUD on comments (reCAPTCHA),
  like/dislike via a first-party `SessionVote` model (`django-vote` was
  tried and is incompatible with Django 5.1 — see its migrations'
  `Meta.index_together`, removed upstream — so it was dropped rather
  than patched).
- **Session proposals & requests**: member-facing forms, model-hook
  email notifications to chapter leads on submission (two bugs found
  and fixed relative to the original ERB mailer templates along the
  way — see git history for `apps/proposals`).
- **Leads namespace** (`/leads/*`): event/session/venue CRUD, CSV
  export and AJAX mass-update of registrations, mailer-task
  create/edit/execute, chapter listing — permission checks re-implemented
  as `require_leader`/`managed_chapter()` decorators in place of CanCan.
- **API v2** (`/api-v2/*`): DRF endpoints matching the original Grape
  API's contract exactly (paths, field shapes, `Authorization: Bearer`
  token auth incl. 401-vs-403 semantics, status codes) — chapters,
  events, event sessions, event registrations, password auth,
  users/me, users/events, users/sessions. The pytest suite's coverage
  pass also caught `UnorderedObjectListWarning` on three of these
  list endpoints — paginating a queryset with no `Meta.ordering` and
  no explicit `.order_by()` can return inconsistent/duplicate rows
  across pages under concurrent writes. Fixed with explicit ordering
  (`apps/api/views.py`).
- **Notifications** (`apps/notifications`): custom leader email blasts
  (`EventMailerTask`, filtered by registration state) and all seven
  automatic-notification modes (Announcement, Speaker Notification,
  Event Reminder, Event Reminder Final/RSVP reminder, Speaker Reminder,
  Admin-on-create, Presentation-update reminder), ported from
  `event_mailer_task.rb` and
  `event_automatic_notification_task.rb` onto real Celery tasks. A
  periodic sweep (`dispatch_event_notifications`, registered in
  `CELERY_BEAT_SCHEDULE`) replaces the original's Resque Scheduler
  one-shot jobs, advancing each public event's `notification_state`
  as its time windows are reached — see the caveat below, this isn't
  actually running automatically in dev.
- **iCal export**: a per-chapter subscribable feed
  (`/chapters/<id>/calendar.ics`, `Chapter#upcoming_events_ics` +
  `Event#to_ics_event`, ported from the `icalendar` gem usage in the
  original), a public venue detail page (`/venues/<id>/`), a "My
  Sessions" page for speakers (`/events/sessions/my_sessions/`), and
  the embedded public Google Calendar page (`/calendar`; the Google
  Groups forum page was removed in Rev 3 — the community no longer
  uses a forum) — these were found missing during a full
  `config/routes.rb` diff against this app's URLs and added since they
  need no external credentials.
- **Yearly community stats** (`/stats`, `/stats/<year>`, optional
  `?chapter_id=`): event counts by type, participation, unique
  speakers, and a speaker leaderboard, ported from
  `app/models/stat.rb` + `StatsController` (`apps/core/stats.py`).
  The original's second "Graph" tab (timeline + pie chart) isn't
  ported — it depended on Google's "Google JSAPI" loader
  (`google.load("visualization", ...)`), a service Google shut down
  years ago, so that tab has been broken in the original app itself
  for a long time regardless of this port.

### Since resolved (this list was from the early port; kept for the record)

Several items previously flagged here have since been built or fixed. For the
authoritative, code-grounded picture see [`docs/FEATURES.md`](docs/FEATURES.md)
and [`docs/rev3-delivery-audit.md`](docs/rev3-delivery-audit.md).

- ✅ **Chapter directory pin map** — built. `Chapter` now carries
  `latitude`/`longitude`; the root directory renders a Google Maps pin map
  (`GOOGLE_MAPS_API_KEY`, env-gated — falls back to the plain grid without a
  key). The `chapters#leaders` / `chapters#upcoming_events` JSON endpoints are
  ported (`leaders_json`, `upcoming_events_json`).
- ✅ **Swagger UI** (`/api-v2/swagger/`) — renders (the CSP now allows the
  `cdn.jsdelivr.net` assets); verified in a real browser.
- ✅ **Social login** — Google OAuth wired via `django-allauth`, env-gated
  (`GOOGLE_OAUTH_CLIENT_ID`/`_SECRET`); buttons on login/signup/landing.
- ✅ **Session library / search** — `/sessions/` (site-wide talk archive with
  tag + `has_reference` filters); legacy `/event_sessions` aliased.
- ✅ **Per-page edit permissions** — `PageAccessPermission` (ReadWrite/ReadOnly)
  enforced at `/pages/<slug>/edit/`.
- ✅ **`/event/:name` alias** — ported as a 301 redirect onto the canonical
  `/events/<id>/`.
- ✅ **Production static/media + CSRF** — `prod.py` fixed (WhiteNoise
  compressed static, S3-or-local media via `STORAGES`, `CSRF_TRUSTED_ORIGINS`);
  CI now runs `manage.py check --deploy` under `config.settings.prod`.

### Intentionally dropped / replaced (Rev 3 decisions)

- **Twitter/IFTTT posting** — dropped; replaced by pluggable broadcast channels
  (Discord/Slack/Telegram webhooks + optional X API v2). The IFTTT path is dead
  upstream.
- **Slack inbound bot** + the legacy pre-Grape `/api/*` (v1) endpoints — dropped
  by design; outbound broadcast + webhooks cover the Slack use case, and the
  rewrite ships only `/api-v2/*`.

### Genuinely still stub / credential-gated / ops-dependent

- **Celery beat** — `dispatch_event_notifications` (time-based reminders) runs
  via `celery -A config beat` + a `worker` in a real deployment
  (`CELERY_BEAT_SCHEDULE` is defined in `base.py`). In dev/showcase,
  `CELERY_TASK_ALWAYS_EAGER=True` runs `.delay()` in-process, so on-demand mail
  fires but scheduled sweeps need beat. By design, not a bug.
- **Google Calendar sync** — a credential-gated stub (`apps/notifications`);
  needs a Google service account + calendar ID. Degrades to no-op without them.
- **Full production boot** — `prod.py` is smoke-checked in CI
  (`check --deploy`) but a real prod boot with `mysqlclient` + real SMTP/S3/
  reCAPTCHA keys is deployment-time; see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
  and [`docs/UPGRADING.md`](docs/UPGRADING.md).

A from-scratch database was created and `migrate`d against with no
manual intervention (`makemigrations --check --dry-run` → "No changes
detected" immediately after), confirming the migration files
themselves are coherent for a new contributor cloning this repo — not
just patched up on the one dev DB this was built against.

See `doc/feature-document.md` in the original repo for the full
feature list this needs to eventually cover, and **Part 8** there for
gaps that existed in the original app too.

## Local Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

docker compose up -d        # MySQL on :3307, Redis on :6380
cp .env.example .env        # or use the defaults already in docker-compose.yml

python manage.py migrate
python manage.py createsuperuser
python manage.py shell < scripts/seed_dev_data.py   # optional dev seed data
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` (or whatever port you pass to `runserver`). Admin at `/admin/`.

### Running the tests

```bash
pip install pytest pytest-django pytest-cov factory-boy faker  # if not already installed
pytest                       # 122 tests, ~2s, 96% coverage across apps/
pytest --cov=apps --cov-report=term-missing   # with a coverage breakdown
```

pytest-django creates and drops a real `test_swachalit` MySQL database
per run (`--reuse-db` in `pytest.ini` keeps it around between runs for
speed — pass `--create-db` once if you need a clean slate). On Python
3.14 specifically, `pip install -r requirements-dev.txt` currently
fails: `safety==3.2.14` pulls in a `pydantic-core` version with no
prebuilt wheel for 3.14, and building it from source fails (PyO3's
release at that pin doesn't support 3.14 yet). That's unrelated to
testing — `safety`/`bandit` are separate lint/security-audit tools —
so install just the packages above rather than the full dev
requirements file if you hit that error.

### Why PyMySQL instead of mysqlclient for local dev

`mysqlclient` needs `libmysqlclient-dev`/`pkg-config` on the host,
which many dev machines won't have (this repo's macOS dev environment
didn't). `config/__init__.py` shims `pymysql.install_as_MySQLdb()` so
the same `django.db.backends.mysql` engine works against either
driver. Production (Dockerfile) installs the real `libmysqlclient-dev`
and can use `mysqlclient` directly if preferred.

## Chapter Sites (multi-tenant, one server)

Each chapter is served as its own website from the same single deployment —
no per-chapter servers, builds, or deployments. A chapter "site" is just
data: the `Chapter` row (with its auto-filled `subdomain` and optional
`custom_domain`) plus its events and pages.

How a request finds its chapter:

1. DNS: `*.null.community` wildcard → the one server; a custom domain
   (`nulldelhi.in`) is a CNAME/ALIAS to the same place.
2. TLS: Caddy (see `deploy/Caddyfile`) holds one wildcard cert for
   `*.null.community` (ACME DNS challenge) and issues per-domain certs
   on demand for custom domains — gated by `GET /domains/check?domain=`,
   which only approves domains registered to an active chapter. This
   gate is what stops strangers pointing domains at the server and
   minting certs from our ACME account.
3. Django: `ChapterSiteMiddleware` reads the Host header and sets
   `request.chapter` (`None` on the root domain = directory site;
   unknown hosts 404). Home/upcoming/archives scope to `request.chapter`;
   templates get `current_chapter` from a context processor.

Config: `ROOT_DOMAIN` (default `localhost`), and in prod set
`SESSION_COOKIE_DOMAIN=.null.community` / `CSRF_COOKIE_DOMAIN` so one
login works across every chapter subdomain (custom domains get their own
session — cookies can't span unrelated domains).

Dev needs no DNS tricks: browsers resolve `*.localhost` to 127.0.0.1, so
`http://delhi.localhost:8000` works out of the box once a chapter named
"Delhi" exists.

## Architecture

```
apps/
  accounts/      User, UserAuthProfile, UserApiToken
  chapters/      Chapter, ChapterLead
  events/        EventType, Event, EventSession, EventSessionComment,
                 EventRegistration, SessionVote, Venue — RSVP, comments,
                 voting views
  content/       Page, PageAccessPermission
  proposals/     SessionProposal, SessionRequest, UserAchievement,
                 email-notification signals
  leads/         chapter-leader namespace: events, sessions, venues,
                 registrations (CSV export, mass update), mailer tasks
  notifications/ EventMailerTask, EventAutomaticNotificationTask, Celery
                 tasks + email templates (see Status above)
  api/           DRF token auth, resource endpoints, schema/Swagger
  core/          shared context processors, home views, template tags
config/
  settings/      base.py, dev.py, prod.py
  celery.py      the actual Celery() app instance (imported from
                 config/__init__.py) — required for @shared_task/.delay()
                 to work at all, not just for CELERY_* settings to apply
templates/        ported from app/views/*.erb
static/           css/, js/, images/ copied verbatim from app/assets/;
                  vendor/ holds locally-hosted Bootstrap 3 + Bootswatch
                  Yeti + Font Awesome 4 (not CDN-loaded, see above)
```

Every model file has a docstring pointing back to the original Rails
model it was ported from (e.g. "See app/models/event.rb") — use that
as the source of truth when implementing the remaining features.

## Documentation

Full docs live in [`docs/`](docs/README.md): architecture, feature catalogue,
data model, local development, deployment, and upgrade/migration paths.

---

*Made with [Claude Code](https://claude.com/claude-code).*
