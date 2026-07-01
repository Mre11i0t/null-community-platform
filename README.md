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
  original model callbacks, reCAPTCHA on the form.
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
  users/me, users/events, users/sessions.
- **Notifications** (`apps/notifications`): custom leader email blasts
  (`EventMailerTask`, filtered by registration state) and all six
  automatic-notification modes (Announcement, Speaker Notification,
  Event/Speaker Reminders, Admin-on-create, Presentation-update
  reminder), ported from `event_mailer_task.rb` and
  `event_automatic_notification_task.rb` onto real Celery tasks. A
  periodic sweep (`dispatch_event_notifications`, registered in
  `CELERY_BEAT_SCHEDULE`) replaces the original's Resque Scheduler
  one-shot jobs, advancing each public event's `notification_state`
  as its time windows are reached — see the caveat below, this isn't
  actually running automatically in dev.

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
  needs a Maps API key and geocoding integration.
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

### Why PyMySQL instead of mysqlclient for local dev

`mysqlclient` needs `libmysqlclient-dev`/`pkg-config` on the host,
which many dev machines won't have (this repo's macOS dev environment
didn't). `config/__init__.py` shims `pymysql.install_as_MySQLdb()` so
the same `django.db.backends.mysql` engine works against either
driver. Production (Dockerfile) installs the real `libmysqlclient-dev`
and can use `mysqlclient` directly if preferred.

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
