# Development

Local development and testing guide for the null Community Platform — a multi-tenant Django rewrite of the null.community *swachalit* platform.

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.12+ | The project image is `python:3.12-slim` (`Dockerfile`). |
| Docker + Docker Compose | For the MySQL 8 and Redis dependencies (`docker-compose.yml`). |
| `pip install -r requirements-dev.txt` | Pulls `requirements.txt` plus dev tooling (pytest, pytest-django, pytest-cov, factory-boy, faker, black, isort, flake8, bandit, safety). |

### No `mysqlclient` needed locally — the PyMySQL shim

`config/__init__.py` installs [PyMySQL](https://pymysql.readthedocs.io/) as a drop-in replacement for the C-based `mysqlclient`:

```python
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
```

The database `ENGINE` in `config/settings/base.py` is still `django.db.backends.mysql`, but this shim lets it talk to MySQL through pure-Python PyMySQL, so you don't need MySQL client headers or a working `mysqlclient` build on your machine. If `mysqlclient` *is* installed it is used as-is; if not, PyMySQL transparently stands in.

## Services (MySQL + Redis)

`docker-compose.yml` defines just the two backing services (not the app itself), both bound to loopback:

| Service | Image | Host port | Notes |
|---|---|---|---|
| `db` | `mysql:8.0` (`linux/amd64`) | `127.0.0.1:3307` → 3306 | database `swachalit`, root password from compose env; volume `ncp-mysql`. |
| `redis` | `redis:7-alpine` | `127.0.0.1:6380` → 6379 | Celery broker. |

```bash
docker compose up -d          # MySQL on :3307, Redis on :6380
```

### Environment

`config/settings/base.py` reads `BASE_DIR/.env` via `django-environ`. Copy the template and the defaults line up with the compose ports:

```bash
cp .env.example .env
```

`.env.example` sets `MYSQL_SERVER=127.0.0.1`, `MYSQL_PORT=3307`, `MYSQL_DATABASE=swachalit`, `MYSQL_USERNAME=root`, `MYSQL_PASSWORD=s0m3p4ssw0rd`, and `REDIS_URL=redis://127.0.0.1:6380/0`. (Without a `.env`, `base.py` defaults to `HOST=db`/`PORT=3306`, which only works from inside the compose network.)

`manage.py` defaults `DJANGO_SETTINGS_MODULE` to `config.settings.dev` — the dev settings enable `DEBUG`, the console email backend, `ACCOUNT_EMAIL_VERIFICATION="optional"`, eager Celery (`CELERY_TASK_ALWAYS_EAGER=True`), and reCAPTCHA test keys (v2 checkbox, always passes) unless real keys are set in the env / `.env` — score-based v3 keys also need `RECAPTCHA_WIDGET=v3` and `localhost` among the key's allowed domains in the Google console. The test suite (`config.settings.test`) always pins the test keys, so real keys in `.env` can't break it. (WSGI/ASGI default to `config.settings.prod`.)

## Migrate & run

```bash
python manage.py migrate
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`; admin at `/admin/`.

## Seed data

Two shell-piped seed scripts populate a dev database:

| Script | Run | Purpose |
|---|---|---|
| `scripts/seed_dev_data.py` | `python manage.py shell < scripts/seed_dev_data.py` | Minimal data to exercise every route in the vertical slice — a chapter (Pune), lead, venue, event, an `EventSession`, an `EventRegistration`, a public profile, and a CMS page. |
| `scripts/seed_rev3_data.py` | `python manage.py shell < scripts/seed_rev3_data.py` | Builds on the above with Rev 3 machinery: chapter subdomains/sites, check-in flags, a full-capacity (waitlist) event, an invite-only (approval queue) event, a just-ended event, CFP proposals, starred sessions, custom questions, and webhook/preference rows. Idempotent. Seed logins use `SEED_PASSWORD` from the env, else a strong random password is generated and printed. |

### Chapter management commands

Under `apps/chapters/management/commands/`:

| Command | What it does |
|---|---|
| `import_null_community` | Imports the real public chapter list from the null.community API v2 (`--base`, `--geocode`, `--activate`); public data only, no member PII. |
| `geocode_chapters` | Fills `Chapter.latitude`/`longitude` for the map from a built-in offline city table, falling back to the Google Geocoding API if a key is set (`--all`, `--force`). |
| `import_bangalore` | Imports the real null Bangalore history (227 past events + 1191 talk sessions) from a local `attendees.db` SQLite workspace (`--db`, `--limit`); signals disabled during import. |
| `import_july2026` | Seeds the upcoming July 2026 null/OWASP Bangalore flagship meetup with the real confirmed agenda, public and accepting registrations for the RSVP/check-in demo. |
| `seed_attendees` | Seeds realistic attendee RSVPs onto Bangalore events, email- and webhook-silent, using non-deliverable `@seed.invalid` accounts (`--pool`, `--per-event`). |
| `add_leader` | Creates or fixes a chapter-lead account (verified email, unusable password so entry is via reset-claim or Google sign-in, active `ChapterLead` row); idempotent (`--name`, `--chapter`, `--send-reset`). |

## Testing

Configuration lives in `pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.test
python_files = tests.py test_*.py
addopts = --reuse-db
```

`config/settings/test.py` extends dev settings with a locmem email backend, the fast MD5 password hasher, and a pinned `REQUIRE_2FA_FOR_PRIVILEGED = False`. `--reuse-db` keeps the `test_swachalit` MySQL database between runs — drop it with `--create-db` after a schema change.

```bash
pytest                                        # full suite, reuses the test DB
pytest --create-db                            # rebuild the schema first
pytest --cov=apps --cov-report=term-missing   # with coverage
```

### Run pytest in a CLEAN shell

The showcase deploy is driven by a sourced `.env` that can set `REQUIRE_2FA_FOR_PRIVILEGED=1`. `django-environ` reads OS environment variables, so if you run pytest **in the same shell** where that `.env` was sourced, the flag would leak into the settings and redirect privileged-page tests into the 2FA setup flow, breaking the suite.

Two guards defend against this, and you should still start from a clean shell to be safe:

1. **`config/settings/test.py`** hard-pins `REQUIRE_2FA_FOR_PRIVILEGED = False` regardless of the env.
2. **`conftest.py`** adds an `autouse` fixture, `_force_2fa_off`, that sets `settings.REQUIRE_2FA_FOR_PRIVILEGED = False` before every test. The single test that exercises 2FA enforcement (`apps/accounts/tests.py`) re-enables it locally via the `settings` fixture, which runs *after* the autouse fixture.

Prefer a fresh terminal that has **not** sourced any showcase `.env`:

```bash
env -i PATH="$PATH" HOME="$HOME" bash -lc 'cd <repo> && pytest'
```

`conftest.py` also carries two other autouse fixtures worth knowing about:

- `bypass_recaptcha` — patches `ReCaptchaField.validate` to skip Google's `siteverify` network call while keeping the "required" check, so a captcha-less POST still fails validation.
- A `BaseContext.__copy__` monkeypatch working around a Django 5.1 / Python 3.14 `super`-proxy copy regression that would otherwise break every templated `test.Client` response. Safe to delete once Django is bumped past the release that fixes `__copy__` upstream.

---

*Made with [Claude Code](https://claude.com/claude-code).*
