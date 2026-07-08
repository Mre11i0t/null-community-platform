# Architecture

`null-community-platform` is a Django rewrite of the null.community **swachalit** platform. Its defining feature is a **multi-tenant chapter-sites model**: one Django deployment serves the root directory site *and* a distinct per-chapter site on every subdomain (and optional custom domain), all backed by a single database and a shared login session.

This document covers the tenant-resolution model, the app layout, settings layering, and the background-job / notification machinery. Everything below is drawn from the code cited inline.

---

## Part 0 — The multi-tenant chapter-sites model

A single WSGI/ASGI process answers for many hostnames. Which tenant a request belongs to is decided **per request, from the `Host` header**, by `apps/chapters/middleware.py::ChapterSiteMiddleware`, which sets `request.chapter`.

### Host resolution

`ChapterSiteMiddleware._resolve()` lowercases `request.get_host()` (port stripped) and compares it against `settings.ROOT_DOMAIN`:

| Host pattern | `request.chapter` | Meaning |
|---|---|---|
| `ROOT_DOMAIN` exactly | `None` | Root / directory site |
| `www`, `testserver`, `127.0.0.1`, `localhost` (`ROOT_ALIASES`) | `None` | Treated as root (dev/tests) |
| `www.<ROOT_DOMAIN>` | `None` | Root |
| `<subdomain>.<ROOT_DOMAIN>` | matched `Chapter` | Chapter site by subdomain |
| exact `custom_domain` | matched `Chapter` | Chapter site by custom apex domain |
| anything else | **`Http404`** | Rejected |

Only **active** chapters match (`Chapter.objects.filter(..., active=True)`). An unknown subdomain or unknown custom domain raises `Http404` rather than silently rendering the root site — the docstring cites cache-poisoning / SEO-duplicate hygiene. This runs *after* Django's own `ALLOWED_HOSTS` host validation; the middleware is host-*routing*, not host-*trust*.

`request.chapter` is exposed to every template via the `apps.chapters.context_processors.current_chapter` context processor (`{"current_chapter": ... or None}`).

### The `Chapter` tenant record

`apps/chapters/models.py::Chapter` (table `chapters`) carries the routing fields:

- `subdomain` — `SlugField(max_length=63, unique=True)`; auto-filled from `slugify(name)` on save if blank.
- `custom_domain` — unique hostname, lowercased/stripped on save (no scheme, no port).
- `active` — gates whether the site resolves at all.
- `latitude` / `longitude` — for the root-directory pin map; filled by the `geocode_chapters` management command.
- `site_url()` — canonical URL of the chapter's own site (custom domain wins over subdomain); scheme/port derive from `SITE_BASE_URL` so emails link correctly in dev and prod.

### `ROOT_DOMAIN` and the shared session cookie

Defined in `config/settings/base.py`:

- `ROOT_DOMAIN` (env, default `localhost`) — the hostname whose subdomains are chapter sites; the bare domain is the root site.
- `SESSION_COOKIE_DOMAIN` / `CSRF_COOKIE_DOMAIN` (env, default `None`) — set to a leading-dot value (e.g. `.null.community`) so **one login works across every chapter subdomain**. `config/settings/showcase.py` documents this explicitly and defaults `CSRF_COOKIE_DOMAIN` to the session value.
- `prod.py` sets `CSRF_TRUSTED_ORIGINS` to `https://<ROOT_DOMAIN>` and `https://*.<ROOT_DOMAIN>` so cross-subdomain form POSTs pass the CSRF Origin check under HTTPS.

### On-demand TLS gate

`config/urls.py` exposes `GET /domains/check` → `apps/chapters/views.py::domain_check`, the gate for Caddy's `on_demand_tls { ask ... }`. Caddy calls it before issuing a certificate for an unknown host; it returns `200 ok` only for `ROOT_DOMAIN`, `www.<ROOT_DOMAIN>`, active-chapter subdomains, or active `custom_domain`s — otherwise `404`. This prevents strangers from pointing arbitrary domains at the server to exhaust the ACME account. It is intentionally cheap and unauthenticated.

---

## Django app layout

Local apps live under `apps/` and are registered in `INSTALLED_APPS` (`config/settings/base.py`). Each mirrors a slice of the original Rails models/controllers.

| App | Responsibility |
|---|---|
| `apps.core` | Shared abstract bases (`TimeStampedModel`, `SoftDeleteModel`/`SoftDeleteQuerySet`), `IncidentReport` (Code-of-Conduct triage), site-config/nav context processors, sitemap/robots views. |
| `apps.accounts` | Custom email-only `User` (table `users`, `AUTH_USER_MODEL`) replacing Devise; allauth integration, signup captcha form, and `Privileged2FAMiddleware`. |
| `apps.chapters` | The tenant model: `Chapter`, host-resolving `ChapterSiteMiddleware`, `domain_check` TLS gate, chapter directory, and import/geocode/leader management commands. |
| `apps.events` | Core domain: `Venue`, `EventType`, `Event` (with the notification state machine), `EventRegistration` (RSVP/waitlist/absent lifecycle), sessions; soft-delete-aware querysets. |
| `apps.content` | CMS-style `Page` (Code of Conduct, Privacy, etc.) with per-user `PageAccessPermission` (ReadWrite/ReadOnly). |
| `apps.proposals` | `SessionProposal` review pipeline (submitted → under review → accepted/rejected/waitlisted → scheduled), emailing the proposer on each transition. |
| `apps.notifications` | Email/broadcast task layer: `EventMailerTask`, `EventAutomaticNotificationTask`, `NotificationPreference`; Celery tasks driving the automatic-notification modes. |
| `apps.leads` | No new tables — permission-gated chapter-leader UI (`/leads/`) over events/chapters/notifications, mirroring the original `Leads::` controller namespace. |
| `apps.api` | No new tables — DRF read/write surface over events/chapters/accounts (`/api-v2/`), token + session auth, drf-spectacular schema. |
| `apps.analytics` | Cookieless, PII-free `PageVisit` traffic attribution via `PageVisitMiddleware`; monthly per-chapter report task. |

### URL routing (`config/urls.py`)

`/admin/`, `/domains/check`, `/sitemap.xml`, `/robots.txt`, `/accounts/` (allauth), `/api-v2/`, `/chapters/`, `/events/`, `/leads/`, plus flat legacy aliases `/venues/<pk>/` and `/event/<slug>` (SEO), and the root-mounted `accounts`, `content`, `proposals`, `core` URLconfs. When `DEBUG`, django-debug-toolbar and dev media serving are added; in prod/showcase with local-disk media, `/media/` is served explicitly (see the `FileSystemStorage` branch).

### Middleware order (`base.py`)

Security → WhiteNoise → Session → Common → CSRF → Auth → Messages → Clickjacking → CSP → Auditlog → allauth Account → **`ChapterSiteMiddleware`** → **`Privileged2FAMiddleware`** (accounts) → **`PageVisitMiddleware`** (analytics). Chapter resolution runs after auth/session so `request.chapter` and `request.user` are both available downstream.

---

## Settings layering

`config/settings/` is a layered hierarchy; `DJANGO_SETTINGS_MODULE` selects the leaf. All are driven by `django-environ` reading `.env` at `BASE_DIR`.

| Module | Inherits | Purpose / key differences |
|---|---|---|
| `base.py` | — | Everything shared: apps, middleware, MySQL (`utf8mb4`), allauth, DRF, CSP, Celery schedule, `ROOT_DOMAIN`, cookie-domain hooks, Rev-3 feature flags. Secrets come from env with safe fallbacks. |
| `dev.py` | `base` | `DEBUG=True`, `ALLOWED_HOSTS=["*"]`, console email, optional debug-toolbar, email verification `optional`, Google's published reCAPTCHA test keys, **`CELERY_TASK_ALWAYS_EAGER=True`**. |
| `test.py` | `dev` | In-memory email backend, fast MD5 password hasher, `REQUIRE_2FA_FOR_PRIVILEGED=False` pinned for the suite. |
| `prod.py` | `base` | `DEBUG=False`, real `ALLOWED_HOSTS`, SSL redirect + HSTS + secure cookies, `CSRF_TRUSTED_ORIGINS` wildcard for subdomains, WhiteNoise compressed static, S3 media when a bucket is set (else local disk), `REQUIRE_2FA_FOR_PRIVILEGED=True`. |
| `showcase.py` | `prod` | Mac Mini + Cloudflare Tunnel demo: trust `X-Forwarded-Proto`, no origin SSL redirect, no HSTS, shared cookie domain, **`CELERY_TASK_ALWAYS_EAGER=True`** (no worker/beat), console email fallback, verification `optional`, test reCAPTCHA keys. |

Notes on storage: Django 5.1's `STORAGES` dict is authoritative (the legacy `STATICFILES_STORAGE`/`DEFAULT_FILE_STORAGE` are ignored). `base.py` uses plain filesystem backends; `prod.py` swaps staticfiles to WhiteNoise's `CompressedStaticFilesStorage` (deliberately **not** the manifest variant, to tolerate dangling vendored-CSS asset refs) and media to S3 when configured.

Sensitive values (DB password, `SECRET_KEY`, OAuth client secrets, Mailgun/WhatsApp/broadcast tokens, reCAPTCHA private key) are all read from the environment and are **not** reproduced here.

---

## Background jobs (Celery)

Celery replaces the original Resque + Resque Scheduler. `config/celery.py` builds the app, pulls config from Django settings under the `CELERY_` namespace, and autodiscovers tasks. The broker is Redis (`REDIS_URL`); results go to the DB (`django-db`); beat uses `django_celery_beat`'s `DatabaseScheduler`.

**Important:** in `dev`, `test`, and `showcase`, `CELERY_TASK_ALWAYS_EAGER=True`, so `.delay()` runs **inline (synchronously)** and there is **no beat process**. The time-based sweeps below only fire when a real `celery -A config beat` is running (prod). During manual testing, call the tasks directly. Both `base.py` and `showcase.py` stress this.

### `CELERY_BEAT_SCHEDULE` (base.py)

| Task | Cadence | What it does |
|---|---|---|
| `apps.notifications.tasks.dispatch_event_notifications` | every 900 s | Advances each public event's notification state machine (below). |
| `apps.events.tasks.auto_mark_absent` | every 900 s | For opted-in events (`auto_absent_enabled` + `check_in_enabled`) past their end, flips confirmed-but-never-checked-in registrations to `Absent`; idempotent via `auto_absent_processed_at`. |
| `apps.events.tasks.send_feedback_requests` | every 1800 s | `FEEDBACK_DELAY_HOURS` after an event ends, emails seat-holders (Confirmed/Absent) a 1–5 rating request, honoring `email_feedback_requests`; idempotent via `feedback_requested_at`. |
| `apps.analytics.tasks.send_monthly_chapter_reports` | 1st of month, 09:00 IST (`crontab`) | Emails each active chapter's leads a 30-day traffic/health/speaker summary. |

`TIME_ZONE` / `CELERY_TIMEZONE` are `Asia/Kolkata`.

### Other tasks

- `send_event_mailer_task` (`apps/notifications/tasks.py`) — implemented; sends a leader-authored blast to a filtered subset of an event's registrations. The task exists, but nothing calls `.delay()` on it automatically yet (the `EventMailerTask` model docstring notes execution is not wired to a trigger).
- `sync_event_to_google_calendar` and `post_to_twitter_via_ifttt` — **documented stubs** that `raise NotImplementedError`; they need service-account / IFTTT webhook credentials that don't exist in this environment and are not wired to any trigger.
- Rev-3 broadcast fan-out (Discord/Slack/Telegram/X) in `_send_announcement` / `_send_event_reminder` replaces the original IFTTT tweet; all channels are env-gated.

---

## The notification state machine

`Event` (`apps/events/models.py`) carries a `notification_state` (`CharField`, default `Init`) plus two boolean gates: `ready_for_notifications` and `ready_for_reminders`. The states port the original `EventNotification` machine:

```
Init → InitialNotifications → Reminder1 → Reminder2 → PresentationUpdate → Finished
```

`dispatch_event_notifications()` is the periodic sweep that advances each **public** event when its time window is reached. For each transition it creates an `EventAutomaticNotificationTask` and dispatches it via `send_automatic_notification.delay(...)`, which routes on the task `mode` to the matching `_send_*` handler.

| From state | Guard | Fires (modes) | To state |
|---|---|---|---|
| `Init` | `ready_for_notifications=True` | `Announcement`, `SpeakerNotification` | `InitialNotifications` (sets `notifications_sent_at`) |
| `InitialNotifications` | `ready_for_reminders=True` **and** `start_time ≤ now + 2 days` | `EventReminder`, `SpeakerReminder` | `Reminder1` |
| `Reminder1` | `ready_for_reminders=True` **and** `start_time ≤ now + 1 day` | `EventReminderFinal` (RSVP reminders to Confirmed attendees, email + WhatsApp per prefs) | `Reminder2` |
| `Reminder2` | `end_time ≤ now − 1 hour` | `PresentationUpdateReminder` (sessions missing a `presentation_url`) | `PresentationUpdate` |
| `PresentationUpdate` | `end_time ≤ now − 7 days` | *(no email — closes the sequence)* | `Finished` |

Each `EventAutomaticNotificationTask` is single-shot (guarded by its `executed` flag), so the sweep is safe to re-run. Individual recipient handlers respect `NotificationPreference` (`email_speaker_notifications`, `email_reminders`, `whatsapp_enabled`, etc.). Announcement/reminder emails go to `NOTIFICATION_ANNOUNCEMENT_ADDRESSES`; the `AdminOnCreate` mode targets `NOTIFICATION_ADMIN_EVENT_CREATE` plus the chapter's leads.

The `EventAutomaticNotificationTask.MODE_*` choices are the canonical list of automatic modes: `Announcement`, `SpeakerNotification`, `EventReminder`, `EventReminderFinal`, `SpeakerReminder`, `AdminOnCreate`, `PresentationUpdateReminder`.

---

## Cross-cutting foundations

- **Soft delete:** `apps.core.SoftDeleteModel` (`deleted_at`) + `SoftDeleteQuerySet.alive()`; the default manager still returns archived rows (admin needs them), so public querysets must call `.alive()`. Events/venues use this.
- **Timestamps:** `TimeStampedModel` (`created_at`/`updated_at`) on every ported table.
- **Auth:** email-only `User`, django-allauth (mandatory email verification in prod, MFA app installed), optional Google/GitHub social login (env-gated — provider apps aren't even installed without credentials).
- **Privileged 2FA:** `REQUIRE_2FA_FOR_PRIVILEGED` (on in prod) makes `Privileged2FAMiddleware` require TOTP for `/leads/` and `/admin/`.
- **Security:** django-csp policy (flat `CSP_*` for the pinned 3.8, plus a 4.x dict kept in sync), auditlog, reCAPTCHA on signup/RSVP/comments.

---

*Made with [Claude Code](https://claude.com/claude-code).*
