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

Feature-complete for the site's core member-facing and chapter-leader
workflows. Read this section before assuming something works — a few
things are genuinely stubbed, and everything here has only been run
against **dev** settings (PyMySQL, `DEBUG=True`, reCAPTCHA test keys,
`CELERY_TASK_ALWAYS_EAGER=True`); the production path (`prod.py`,
`mysqlclient`, `collectstatic`, real email/SMTP, real reCAPTCHA keys)
has not been exercised.

A 122-test pytest suite (96% coverage across `apps/`, one `tests.py`
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
  the embedded public Google Calendar / Google Groups forum pages
  (`/calendar`, `/forum`) — these were found missing during a full
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

### Explicitly NOT done or only partially done

- **Celery beat is not started in dev.** `dispatch_event_notifications`
  (the time-based reminder scheduler) and the Celery worker in general
  only run because `CELERY_TASK_ALWAYS_EAGER=True` makes `.delay()`
  execute synchronously in-process. Nothing calls
  `dispatch_event_notifications` on a schedule unless you run
  `celery -A config beat` (and a separate `celery -A config worker` in
  a real, non-eager deployment) alongside the Django process.
- **Google Calendar sync** (`Event#event_update_calendar`) and
  **Twitter/IFTTT posting** (`IftttMailer`): left as
  `NotImplementedError` stubs in `apps/notifications/tasks.py`, not
  wired to any trigger. Both need credentials this environment doesn't
  have (a Google service account + calendar ID, an IFTTT Maker webhook
  key) — not faked.
- **Chapter map** (homepage + chapter directory): the original used a
  live Google Maps pin map via Geocoder. Left out rather than faked —
  needs a Maps API key and geocoding integration. Its two supporting
  JSON endpoints (`chapters#leaders`, `chapters#upcoming_events`)
  aren't ported either for the same reason; the same data is already
  available server-rendered on the chapter detail page.
- **Swagger UI** (`/api-v2/schema/swagger/`) renders blank in this
  sandbox's browser automation tool because `swagger-ui-dist`'s CDN
  (jsdelivr) 503s through that specific network path; the underlying
  `/api-v2/schema/` OpenAPI JSON was verified directly and is correct.
  Likely fine in a normal browser — flagged here because it wasn't
  confirmed in one.
- **Production settings are unverified.** `prod.py` (real
  `mysqlclient`, `DEBUG=False`, `collectstatic`, SMTP email, real
  reCAPTCHA keys, S3/whatever static storage) has not been booted or
  tested this session — only `dev.py` has.
- **Social login (`/auth/:provider/callback`)**: `django-allauth`'s
  social-account app is not configured with any OAuth client
  credentials — the `UserAuthProfile` model (schema equivalent) exists
  but no provider is wired up.
- **Slack integration** (`/api/slackbot/events`) and the old pre-Grape
  `/api/*` endpoints (`authenticate`, `check_authentication`,
  `user_registrations`, `user_autocomplete`): not ported. The `/api/*`
  ones are superseded in spirit by `/api-v2/*` (password auth, per-user
  events/sessions); `user_autocomplete`'s job (speaker search when
  leads create sessions) is covered client-side in
  `templates/leads/event_sessions/form.html`. Slack needs a bot token
  this environment doesn't have. `/api/register` in the original
  routes has no controller action at all — a dead route even there.
- **Session library / search page** (`/event_sessions` — browse and
  full-text-search all past sessions site-wide, distinct from the
  per-user "My Sessions" page above): not built. Still linked as
  "(coming soon)" in the nav.
- **Per-page edit permissions**: the original let non-admin users with
  a `PageAccessPermission` row edit specific CMS pages in place
  (`/pages/:id/edit`). Django admin can edit `Page` rows for staff
  users, which covers the admin case but not that narrower
  per-page-per-user grant — not ported.
- **`/event/:name` SEO-friendly event URL** (slug-based alias for
  `/events/:id`): not ported: low-value, `/events/<id>/` covers the
  same page.

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
