# Contributing

Thanks for helping keep the null community platform alive. This is a Django
rewrite of the original Rails **swachalit** app — the goal is a codebase a
mostly-Python community can actually maintain.

## Quick start

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for the full setup. In short:

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # PyMySQL shim → no mysqlclient build
docker compose up -d db redis
python manage.py migrate
python manage.py shell < scripts/seed_rev3_data.py
python manage.py runserver
```

## Before you open a PR

1. **Run the tests in a clean shell** — `python -m pytest`. Do *not* source a
   deployment `.env` into the shell running pytest (it can leak
   `REQUIRE_2FA_FOR_PRIVILEGED=1` and redirect privileged-page tests; the
   conftest guards this, but keep the shell clean).
2. **Add a test** for any behaviour change — the suite is what makes this
   codebase safe to modify. Put one real-path test next to the code it covers.
3. **`makemigrations --check`** — commit migrations with model changes.
4. **No secrets** — never commit credentials. `.env` and
   `deploy/showcase/.env.showcase` are gitignored; use env vars.
5. **No hardcoded deployment domain** — use `ROOT_DOMAIN`/`request.get_host`,
   not a literal host. CI + the secret scan will catch leaks.

## Style

Match the surrounding code — it favours small, well-commented functions and
Django conventions. Templates use Bootstrap 3 (Bootswatch Yeti); keep the
visual language uniform (no per-chapter theming — a deliberate decision).

## Where things live

| Area | Path |
|---|---|
| Apps | `apps/<name>/` (models, views, urls, tests) |
| Settings | `config/settings/{base,dev,test,prod,showcase}.py` |
| Management commands | `apps/chapters/management/commands/` |
| Templates | `templates/` |
| Docs | `docs/` |

## Reviews & CI

Every PR runs the test suite, a migrations check, a prod-settings deploy check,
CodeQL, and a secret scan (`.github/workflows/`). Green CI is required.

---

*Made with [Claude Code](https://claude.com/claude-code).*
