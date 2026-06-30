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

This is an early-stage rewrite, not a finished replacement. Read this
section before assuming a feature works.

### Working end-to-end (booted, migrated, manually verified against seeded data)

- Django project skeleton, settings split (`config/settings/{base,dev,prod}.py`)
- Full data model for: users, chapters, chapter leads, venues, event
  types, events, event sessions, session comments, event
  registrations, pages, page permissions, session proposals, session
  requests, user achievements, event mailer tasks, automatic
  notification tasks — every table in the original `db/schema.rb` has
  a Django model with matching fields.
- Django admin registered for every model above, modeled on the
  original ActiveAdmin resources (list filters, batch actions for
  registration state changes, autocomplete for FK pickers).
- Public pages, rendered from templates ported line-by-line from the
  original ERB views (not reinvented):
  - `/` homepage
  - `/upcoming` upcoming events
  - `/archives` paginated past events
  - `/about`, `/privacy` static pages
  - `/chapters/` chapter directory with client-side search
  - `/chapters/<id>/` chapter detail (leaders, upcoming/past events)
  - `/events/<id>/` event detail (sessions, venue, registration state)
  - `/events/sessions/<id>/` session detail (abstract, speaker, resources)
  - `/profile/<id>/` public user profile (sessions delivered/attended)
  - `/pages/<slug>/` dynamic CMS pages

### Explicitly NOT done — scaffolded or stubbed, do not assume these work

- **Auth flows**: django-allauth is installed and wired into
  settings/urls, but signup/login/email-confirmation have not been
  tested end-to-end against the new User model.
- **Event registration (RSVP) actions**: the registration *state* and
  *display* are wired up; the create/cancel registration views/forms
  are not implemented yet.
- **Leads namespace** (chapter-leader event/session/venue management,
  CSV export, mass registration update): not started. The original
  `/leads/*` controllers have no Django equivalent yet.
- **Session proposals/requests forms**: models exist; no views/forms.
- **Comments & voting on sessions**: models exist (`EventSessionComment`,
  `django-vote` installed); no views.
- **Background jobs**: `apps/notifications/tasks.py` is a Celery
  scaffold with `NotImplementedError` stubs — mailer task delivery,
  automatic notifications, Google Calendar sync, and the IFTTT
  Twitter integration all need to be ported from
  `app/models/event_notification.rb` and the mailer classes.
- **API v2**: only the DRF schema/Swagger endpoints are wired
  (`/api-v2/schema/`, `/api-v2/schema/swagger/`). The actual resource
  endpoints (chapters, events, sessions, registrations, users/me,
  password auth) are not implemented — see `apps/api/urls.py`.
- **Chapter map** (homepage + chapter directory): the original used a
  live Google Maps pin map via Geocoder. Intentionally left out
  rather than faked — needs a Maps API key and geocoding integration.
- **reCAPTCHA**: `django-recaptcha` is installed but not wired into
  any form yet (no forms exist yet for the things that needed it:
  signup, RSVP, comments).

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

Visit `http://127.0.0.1:8000/`. Admin at `/admin/`.

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
                 EventRegistration, Venue
  content/       Page, PageAccessPermission
  proposals/     SessionProposal, SessionRequest, UserAchievement
  notifications/ EventMailerTask, EventAutomaticNotificationTask,
                 Celery task scaffolds
  api/           DRF token auth, schema/Swagger
  core/          shared context processors, home views, template tags
config/
  settings/      base.py, dev.py, prod.py
templates/        ported from app/views/*.erb
static/           copied verbatim from app/assets/ (CSS/JS/images)
```

Every model file has a docstring pointing back to the original Rails
model it was ported from (e.g. "See app/models/event.rb") — use that
as the source of truth when implementing the remaining features.
