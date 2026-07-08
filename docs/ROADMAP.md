# Roadmap & Improvement Ideas

The Rev 3 roadmap is delivered (see [rev3-delivery-audit.md](rev3-delivery-audit.md)).
This is the *next* backlog — deliberately-deferred product features plus
engineering improvements that would strengthen the codebase.

## Deferred product features (from the PRD, not yet built)

These were explicitly **not selected** for Rev 3 — pick them up when there's
demand:

- Paid ticketing tiers (Razorpay/Stripe), refunds, invoices
- Group / +1 registration against the capacity cap
- Per-session / per-track capacity
- Printable badge PDF sheets
- Web push notifications (per-user opt-in)
- Chapter digest subscriptions (follow without registering)
- Virtual / hybrid: meeting-link integration, live-stream embed, hybrid
  attendance types, recording auto-attach
- Multi-track agenda builder with conflict detection
- Certificates (verifiable attendance/speaker, QR)
- Per-chapter CMS pages & custom nav
- Embeddable "upcoming events" widget
- PWA / installable app shell
- AI assists (draft descriptions, suggest tags, summarize recordings)

## Credential-gated integrations (built, need keys)

Wire these by setting env vars — code degrades gracefully without them:

- **Mailgun** real email (`MAILGUN_API_KEY` / `MAILGUN_SENDING_KEY`)
- **Google Calendar** sync (service account)
- **S3** media storage (`AWS_STORAGE_BUCKET_NAME`)
- **Google/GitHub OAuth** (client id/secret) + authorized redirect URIs
- **Sentry** error tracking (`SENTRY_DSN`)
- Broadcast channels: Discord / Slack / Telegram webhooks, optional X API v2

## Engineering improvements

### Data quality
- Imported archive sessions are attributed to a shared "archive" speaker
  (source had no speaker↔session links). If richer data becomes available, map
  sessions to real speaker profiles.

### Frontend / assets
- The vendored Bootstrap/Bootswatch CSS has a few dangling asset references,
  which is why static uses WhiteNoise's non-manifest storage. Fix the dangling
  refs, then switch to `CompressedManifestStaticFilesStorage` for hashed
  cache-busting (`config/settings/prod.py`).
- Google Maps uses the deprecated `google.maps.Marker`; migrate to
  `AdvancedMarkerElement` and add `loading=async` to the loader.
- Consider bumping `django-csp` to 4.x (config already carries the 4.x dict
  form alongside the active 3.8 flat settings — see `config/settings/base.py`).

### Platform
- Add a `LICENSE` file (the project has none yet — a maintainer decision;
  MIT/Apache-2.0 are common for community platforms).
- Kubernetes manifests for a scaled deploy (the original swachalit shipped
  `kubernetes/`; this fork ships Docker + Caddy).
- Rate limiting on auth/RSVP endpoints.
- Background-job monitoring UI (Celery results are stored; a dashboard would
  help leads).
- Read-replica support for the analytics/stats queries at scale.

### Testing / CI
- Add coverage reporting to CI and a coverage gate.
- Add a Playwright/Selenium smoke suite for the critical UI flows (login, RSVP,
  check-in) to complement the request-level tests.
- Add `semgrep` SAST to match swachalit's security workflow set.

## How to propose more

Open an issue describing the problem (not just the solution), or add to this
file in a PR. See [CONTRIBUTING.md](../CONTRIBUTING.md).

---

*Made with [Claude Code](https://claude.com/claude-code).*
