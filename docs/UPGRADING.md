# Upgrading & Migration

The whole reason this project exists is that the original Rails **swachalit**
rotted: Ruby 2.6 / Rails 4.2, abandoned gems, broken on ARM64. This document
exists so **that never happens again**. Keep dependencies moving and the
codebase stays alive.

## Guiding principles

1. **Small, frequent bumps beat big-bang rewrites.** Dependabot (see
   `.github/dependabot.yml`) opens weekly PRs; merge them when CI is green.
2. **The test suite is the safety net.** 200+ tests gate every upgrade — never
   merge an upgrade with red CI.
3. **Settings and secrets are environment-driven.** Nothing about a deployment
   is hardcoded, so migrating hosts/domains is a config change, not a code
   change.
4. **One database schema.** Multi-tenancy is row-level (`request.chapter`), not
   schema-per-tenant, so there is a single migration history to reason about.

## Routine dependency upgrades

```bash
source venv/bin/activate
pip list --outdated                        # see what's behind
pip install -U <package>                    # or merge the Dependabot PR
python -m pytest                            # must stay green
python manage.py makemigrations --check     # no surprise schema drift
```

Pin new versions in `requirements.txt` / `requirements-dev.txt`. Group-merge
the Django-family PRs together (they're versioned in lockstep).

## Upgrading Django

Django has a well-defined deprecation path; follow it:

1. Read the release notes for the target version's "Backwards incompatible
   changes" and "Features deprecated".
2. Run `python -W error::DeprecationWarning -m pytest` on the **current**
   version first — fix every `RemovedInDjangoXWarning` before bumping.
3. Bump `Django==` one **feature release** at a time (e.g. 5.1 → 5.2 → 6.0),
   running the suite after each.
4. Re-run `python manage.py check --deploy` under `config.settings.prod`.
5. Known shim to watch: `conftest.py` + `apps/core/compat.py` patch
   `BaseContext.__copy__` for a Python-3.14/Django-5.1 interaction. Once Django
   ships a 3.14-safe `__copy__`, delete both (they become harmless dead code) —
   a comment in each says so.

### LTS strategy

Django LTS releases (e.g. 5.2 LTS) get ~3 years of security fixes. Targeting the
current LTS between feature-chasing is a reasonable low-maintenance posture.

## Upgrading Python

- Target is **3.12+**; the `Dockerfile` pins `python:3.12-slim`.
- Local dev may run newer (this repo has been exercised on 3.14 — hence the
  `BaseContext` shim). To bump the floor: change the `Dockerfile` base image and
  the `ci.yml` `python-version`, run the suite on the new interpreter, and drop
  shims the new version makes unnecessary.
- The **PyMySQL shim** (`config/__init__.py` → `pymysql.install_as_MySQLdb()`)
  lets you avoid `mysqlclient`'s C build entirely; keep it unless you
  deliberately move to `mysqlclient` in prod (then guard the shim behind a flag).

## Upgrading the database

- Engine: MySQL 8 (`utf8mb4`). Bumping MySQL is an ops change; run migrations
  against a copy first.
- Schema changes are ordinary Django migrations. After any model change:
  `makemigrations` → review → `migrate`. In CI the `makemigrations --check`
  step fails if a migration is missing.
- **`--reuse-db` gotcha:** after a schema change, run pytest once with
  `--create-db` so the reused test DB picks up new columns.

## Migrating the deployment

Because everything is env-driven, moving between hosts/providers is mechanical:

| From → To | What changes |
|---|---|
| Showcase (Mac Mini + Cloudflare Tunnel) → VPS | Point DNS at the VPS, run the `Dockerfile` + `deploy/Caddyfile` (wildcard TLS). No code change. |
| Local disk media → S3 | Set `AWS_STORAGE_BUCKET_NAME` (+ creds); `config.settings.prod` switches the `STORAGES["default"]` backend automatically. |
| Console email → Mailgun | Set `MAILGUN_API_KEY`/`MAILGUN_SENDING_KEY` + `MAILGUN_SENDER_DOMAIN`; the backend flips to Anymail. |
| New root domain | Set `ROOT_DOMAIN`, `ALLOWED_HOSTS`, `SESSION_COOKIE_DOMAIN`, `CSRF_TRUSTED_ORIGINS`. Nothing hardcodes the domain. |
| New chapter | One `Chapter` row + a DNS record. Live in minutes (PRD Part 0). |

### Data portability

- The public data importers (`import_null_community`, `import_bangalore`) show
  how to ingest from an external source; they're idempotent (`get_or_create`).
- Standard Django `dumpdata`/`loaddata` works for fixtures. For full backups,
  back up the MySQL database + the media directory (or S3 bucket).

## If an upgrade breaks

1. CI red? Read the failing test — it names the behaviour that changed.
2. Revert the single dependency bump, reproduce locally, fix forward with a test.
3. Never disable a test to make CI green; fix the code or the test's assumption.

---

*Made with [Claude Code](https://claude.com/claude-code).*
