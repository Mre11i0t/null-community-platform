# Features

A catalog of what the null Community Platform does, grouped by audience. The
platform is a Django 5 rewrite of the Rails "swachalit" app that powers
[null.community](https://null.community). Chapter sites are multi-tenant on one
server (subdomain / custom-domain routing, resolved per request into
`request.chapter`). "Rev 3" marks features added beyond the original 1:1 Rails
port; those are called out in-line.

Route conventions used below:

- Root-site and shared routes are absolute (e.g. `/chapters/`).
- Chapter-leader tooling lives under `/leads/` (`apps/leads/urls.py`).
- The read/write JSON API lives under `/api-v2/` (`apps/api/urls.py`).

---

## Guest (unauthenticated)

Public, tenant-aware browsing. On a chapter host, the home / archive / session
views are scoped to that chapter's own content; on the root site they span the
whole community.

| Feature | Route | Notes |
|---|---|---|
| Home / landing | `/` (`core:home`) | Tenant-aware; chapter home on a chapter host |
| Upcoming events | `/upcoming` (`core:upcoming`) | |
| Event archives | `/archives` (`core:archives`) | Past events |
| Community calendar | `/calendar` (`core:calendar`) | |
| Session search | `/sessions/` (`core:session_search`) | Legacy alias `/event_sessions` preserved |
| About / Privacy | `/about`, `/privacy` | |
| Yearly stats | `/stats`, `/stats/<year>` (`core:stats_index`, `stats_show`) | |
| Chapter directory | `/chapters/` (`chapters:list`) | Rev 3: pin-map of chapters (lat/long geocoded) |
| Chapter directory data | `/chapters/<id>/leaders`, `/chapters/<id>/upcoming_events` | JSON feeds for the map/detail cards |
| Chapter detail | `/chapters/<id>/` (`chapters:detail`) | |
| Chapter calendar feed | `/chapters/<id>/calendar.ics` | iCal subscription |
| Event detail | `/events/<id>/` (`events:detail`); SEO alias `/event/<slug>` | |
| Event calendar file | `/events/<id>/calendar.ics` (`events:event_ics`) | |
| Session detail | `/events/sessions/<id>/` (`events:session_detail`) | |
| Venue detail | `/venues/<id>/` (`venue_detail`) | Flat route matching the original |
| Static content pages | `/pages/<slug>/` (`content:page_detail`) | CMS pages, access-controlled |
| "Start a chapter" | `/start-a-chapter` (`core:start_chapter`) | |
| Sign up / log in | `/accounts/…` (django-allauth) | Email + password; Rev 3 Google/GitHub login (env-gated) |

**SEO (Rev 3, host-scoped).** Per-chapter `sitemap.xml` and `robots.txt` are
served at the root of each host (`core:sitemap`, `core:robots`), reflecting that
each chapter has its own canonical domain rather than one site-wide domain.
Pages emit canonical URLs, Open Graph tags, and JSON-LD.

**Cookieless analytics (Rev 3).** `PageVisitMiddleware`
(`apps/analytics/middleware.py`) records each visit — host, path, referrer
domain, UTM params, resolved chapter — with **no** user id, IP, or fingerprint,
so it stays out of consent/DPDP/GDPR territory (`apps/analytics/models.py`).

---

## Member (authenticated user)

### Profile & account

| Feature | Route | Notes |
|---|---|---|
| Public profile | `/profile/<id>/` (`accounts:public_profile`) | Social links, talks, achievements |
| Edit profile | `/settings/profile` (`accounts:profile_edit`) | Name, handle, avatar, social/homepage, about |
| My RSVPs | `/my_rsvps` (`accounts:my_rsvps`) | |
| Notification preferences | `/settings/notifications` (`accounts:notification_preferences`) | Rev 3 preference center (below) |
| Add achievement | `/settings/achievements/new` (`accounts:add_achievement`) | Self-reported bug/bounty/OSS/community achievements |
| Export my data | `/settings/export.json` (`accounts:export_data`) | Rev 3: self-service JSON data export |
| Delete account | `/settings/delete-account` (`accounts:delete_account`) | Rev 3: anonymize-and-deactivate (see below) |
| Report an incident | `/report-incident` (`accounts:report_incident`) | Rev 3 CoC incident reporting (below) |
| Social login | `/accounts/…` | Rev 3: Google / GitHub OAuth, enabled only when client IDs are configured |

**Account anonymization (Rev 3, `User.anonymize_and_deactivate`).** Deletion
keeps history rows (registrations, comments, talks) but repoints them at an
anonymized shell — email/name/handle/social/homepage/about/avatar cleared,
password unusable, API tokens and allauth email addresses purged.

**Notification preference center (Rev 3, `NotificationPreference`).** Per-user
toggles for email reminders, speaker notifications, and feedback requests, plus
an opt-in WhatsApp number (E.164). Transactional mail (confirmation, password
reset, lead mailer tasks) is always delivered regardless of preferences.

### Events & registration

| Feature | Route | Notes |
|---|---|---|
| RSVP / register | `/events/<id>/registrations/new/` (`events:registration_new`) | Rev 3: answers custom questions; waitlists when full |
| Cancel registration | `/events/<id>/registrations/<pk>/cancel/` (`events:registration_destroy`) | Cancelling inside `cancellation_deadline_hours` counts as a no-show |
| Attendee list | `/events/<id>/registrations/` (`events:registration_index`) | |
| Registration QR pass | `/events/<id>/registrations/<pk>/qr.png` (`events:registration_qr`) | Rev 3: personal check-in QR |
| Post-event feedback | `/events/<id>/feedback/` (`events:event_feedback`) | Rev 3: 1–5 rating + comment, one per attendee |
| Event discussion | `/events/<id>/comments/new/` (`events:event_comment_create`) | Rev 3: pre/post-event Q&A thread on the event |
| Photo gallery upload | `/events/<id>/photos/upload/` (`events:event_photo_upload`) | Rev 3: event photo gallery |

**Registration states (`EventRegistration`).** `Provisional`, `Confirmed`,
`Not Attending`, `Absent`, and Rev 3 `Waitlisted`. Only Provisional/Confirmed
hold a seat.

**Waitlist (Rev 3).** When an event is at `max_registration`, new RSVPs are
saved as `Waitlisted` (FIFO). Freed seats auto-promote the next person and email
them (`Event.promote_from_waitlist`); members can see their `waitlist_position()`.

**Invite-only / approval queue (Rev 3).** Events whose `event_type` requires an
invitation (`Event.invite_only()`) route RSVPs into a leader approval queue; the
member's RSVP button reads "Register" rather than "RSVP".

**Custom RSVP questions (Rev 3).** Leaders define extra questions
(`Event.custom_questions`, a list of `{label, required}`); answers are stored on
`EventRegistration.custom_answers`.

**No-show strikes (Rev 3).** Registrations marked `Absent` inside a rolling
window (`NO_SHOW_WINDOW_DAYS`, default 180) count as strikes; reaching
`NO_SHOW_STRIKE_LIMIT` (default 3) blocks further RSVPs
(`User.no_show_strikes()`, `User.rsvp_blocked()`).

**Versioned Code of Conduct (Rev 3).** Acceptance is tracked per CoC version
(`CocAcknowledgement`, unique per user+version); a version bump (`COC_VERSION`)
re-prompts everyone. `User.has_acknowledged_coc()` / `acknowledge_coc()`.

### Sessions, talks & agenda

| Feature | Route | Notes |
|---|---|---|
| My sessions (as speaker) | `/events/sessions/my_sessions/` (`events:my_sessions`) | |
| Confirm speaking | `/events/sessions/<id>/confirm/` (`events:session_confirm`) | Rev 3: explicit speaker confirmation (`speaker_confirmed_at`) |
| Personal agenda | `/events/sessions/my_schedule/` (`events:my_schedule`) | Rev 3: starred sessions timetable |
| Agenda calendar feed | `/events/sessions/my_schedule.ics` (`events:my_schedule_ics`) | Rev 3 |
| Star / unstar a session | `/events/sessions/<id>/star/` (`events:session_star`) | Builds the personal agenda |
| Like / dislike a session | `/events/sessions/<id>/like/`, `…/dislike/` | `SessionVote` |
| Session comments | `/events/sessions/<id>/comments/new/` + edit/delete | |
| Ask a session question | `/events/sessions/<id>/questions/new/` (`events:question_create`) | Rev 3 live Q&A |
| Upvote a question | `/events/questions/<id>/upvote/` (`events:question_upvote`) | Rev 3: ranked by upvotes |

**Co-speakers (Rev 3).** A session credits a primary speaker (`user`) plus
`co_speakers` (M2M); `all_speakers()` returns primary-first (`EventSession`).

**Session Q&A (Rev 3, `SessionQuestion`).** Audience questions per session,
ranked by upvotes; server-rendered (reload to refresh), leads can hide
off-topic ones.

### Proposals & CFP

| Feature | Route | Notes |
|---|---|---|
| Browse my proposals | `/session_proposals/` (`proposals:proposal_index`) | |
| Submit a proposal | `/session_proposals/new/` (`proposals:proposal_new`) | To a chapter, for an event type |
| View / edit a proposal | `/session_proposals/<id>/`, `…/edit/` | |
| Suggest a topic (request) | `/session_requests/new/` (`proposals:request_new`) | Community-suggested topic |

**CFP pipeline (Rev 3, `SessionProposal`).** Proposals move through
`submitted → under_review → accepted / rejected / waitlisted → scheduled`, and
every transition emails the proposer (`set_status`) — the original submitted
into a void.

### Gamification (Rev 3, chapter sites)

Points and badges are **computed live** from real activity, not stored
(`apps/core/gamification.py`): attended = 10, talk = 50, co-talk = 25 points.
Badges: First Talk (≥1 talk), Veteran Speaker (≥5), Regular (≥5 attended),
Community Pillar (≥25). The chapter leaderboard lives at `/leaderboard`
(`core:leaderboard`) and 404s on the root site — points are a per-chapter thing.

### Trust & safety

- **Incident reporting (Rev 3, `IncidentReport`):** `/report-incident` files a
  confidential CoC report (description, where, contact-ok flag), emailed to the
  response team and triaged admin-only through states open → reviewing →
  resolved. No public views.

---

## Chapter Leader (`/leads/`)

Chapter-scoped management console (`apps/leads/urls.py`). Access is limited to
active chapter leads (`User.is_leader()` / `managed_chapters()`); when
`REQUIRE_2FA_FOR_PRIVILEGED` is on, leads must have TOTP 2FA to enter `/leads/`.

### Events

| Feature | Route |
|---|---|
| Event dashboard / index | `/leads/events/` |
| Create / edit / delete event | `/leads/events/new/`, `/leads/events/<id>/edit/`, `…/delete/` |
| Publish event | `/leads/events/<id>/publish/` |
| Event overview | `/leads/events/<id>/` |

### Check-in (Rev 3, per-event opt-in via `check_in_enabled`)

| Feature | Route |
|---|---|
| Check-in dashboard | `/leads/events/<id>/check_in/` |
| Scanner (scan QR) | `/leads/events/<id>/check_in/scan/` |
| Manual mark check-in | `/leads/events/<id>/check_in/mark/` |
| Live stats (JSON) | `/leads/events/<id>/check_in/stats.json` |
| Self-serve kiosk | `/leads/events/<id>/kiosk/<token>/` |

Each registration carries a unique `check_in_code` and `checked_in_at`. When
`auto_absent_enabled` is set, a post-event sweep marks no-shows `Absent`
(`auto_absent_processed_at` for idempotency), which feeds the no-show-strike
system.

### Registrations

| Feature | Route |
|---|---|
| Registration list | `/leads/events/<id>/registrations/` |
| Approval queue (invite-only) | `/leads/events/<id>/registrations/approval/` |
| Approve / reject one | `/leads/events/<id>/registrations/approval/<pk>/` |
| Export CSV | `/leads/events/<id>/registrations/export_csv/` |
| Bulk state update | `/leads/events/<id>/registrations/mass_update/` |

### Sessions

| Feature | Route |
|---|---|
| Session index | `/leads/events/<id>/sessions/` |
| New / edit / delete session | `/leads/events/<id>/sessions/new/`, `…/<pk>/edit/`, `…/delete/` |
| Suggest a speaker (autocomplete) | `/leads/events/<id>/sessions/suggest_user/` |
| Bulk delete sessions | `/leads/events/<id>/sessions/mass_delete/` |
| Speaker search | `/leads/speakers/search/` |

### Communications

| Feature | Route | Notes |
|---|---|---|
| Mailer tasks (index/new/show/edit) | `/leads/events/<id>/mailer_tasks/…` | Targeted email blast to a filtered registration subset (`EventMailerTask`) |
| Test-send a mailer task | `/leads/events/<id>/mailer_tasks/<pk>/test_send/` | |
| Execute a mailer task | `/leads/events/<id>/mailer_tasks/<pk>/execute/` | |
| Notification log | `/leads/notifications/` | Automatic notification modes: announcement, speaker notification, reminders, admin-on-create, presentation-update (`EventAutomaticNotificationTask`) |

**Broadcast channels (Rev 3, `apps/notifications/broadcast.py`).** One message
fans out to every configured channel — Discord, Slack, Telegram (webhook-based),
and X — replacing the dead Twitter-via-IFTTT path. Each channel is env-gated;
unconfigured channels silently skip and one failing channel never stops the rest.

### Webhooks (Rev 3)

| Feature | Route |
|---|---|
| Webhook endpoints | `/leads/webhooks/` |
| Delete endpoint | `/leads/webhooks/<pk>/delete/` |

Chapter-registered URLs receive **HMAC-signed** JSON for platform events
(`WebhookEndpoint`, auto-generated secret); every attempt is recorded in
`WebhookDelivery` (kind, payload, response status, error) for visibility.

### Venues, proposals, analytics & chapter settings

| Feature | Route |
|---|---|
| Venues (index/new/show/edit/delete) | `/leads/venues/…` |
| Proposal review queue | `/leads/proposals/` |
| Review a proposal | `/leads/proposals/<pk>/` |
| Analytics dashboard | `/leads/analytics/` |
| Event types | `/leads/event_types/` |
| Chapter list / edit | `/leads/chapters/`, `/leads/chapters/<pk>/edit/` |

**Proposal reviewing (Rev 3, `ProposalReview`).** One 1–5 score + comment per
reviewer per proposal (unique per reviewer); `average_score()` drives ranking.

**Chapter analytics (Rev 3).** Per-chapter dashboard from the cookieless
`PageVisit` data — traffic by host, top referrers, and an attendance funnel
(registered → confirmed → checked-in), plus a monthly chapter report emailed via
a Celery beat task (`apps/analytics/services.py`, `tasks.py`).

---

## Admin (Django admin, `/admin/`)

- Django admin is registered for **every** table in the original schema (list
  filters, batch actions) — the platform's back-office. Includes triage of
  Rev 3 `IncidentReport` records (open → reviewing → resolved), which have no
  public surface.
- **TOTP 2FA (Rev 3)** via `allauth.mfa`. With `REQUIRE_2FA_FOR_PRIVILEGED`
  enabled, chapter leads must have TOTP to use `/leads/` and staff to use the
  admin.
- **Management commands** (`apps/chapters/management/commands/`): `add_leader`,
  `geocode_chapters` (fills chapter lat/long for the pin-map), `seed_attendees`,
  and data importers `import_bangalore`, `import_july2026`,
  `import_null_community`.

---

## API v2 (`/api-v2/`)

Successor to the original Grape `/api-v2` mounted API (`apps/api/urls.py`).
Custom token auth via `ApiTokenAuthentication` (`apps/api/authentication.py`),
backed by `UserApiToken` (24-hour default expiry). OpenAPI schema and Swagger UI
are served via drf-spectacular.

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api-v2/schema/` | GET | public | OpenAPI schema |
| `/api-v2/swagger/` | GET | public | Swagger UI |
| `/api-v2/chapters/` | GET | public | List chapters |
| `/api-v2/events/` | GET | public | List events |
| `/api-v2/events/<id>/event_sessions/` | GET | public | Sessions for an event |
| `/api-v2/events/<id>/event_registrations/` | GET | public | Registrations for an event |
| `/api-v2/authentications/password/` | POST | public | Exchange email + password for an API token |
| `/api-v2/users/me/` | GET | token | Current user |
| `/api-v2/users/events/` | GET | token | Current user's events |
| `/api-v2/users/sessions/` | GET | token | Current user's sessions |

---

## Infrastructure notes

- **Multi-tenancy:** one server hosts every chapter site by subdomain
  (`<subdomain>.<ROOT_DOMAIN>`) or custom apex domain; `Chapter.site_url()`
  resolves the canonical URL (custom domain wins). `/domains/check`
  (`chapter_views.domain_check`) is the cheap, unauthenticated gate for Caddy
  on-demand TLS.
- **Async:** Celery + beat drive waitlist promotion emails, auto-absent sweeps,
  feedback-request emails, webhook delivery, broadcasts, and the monthly
  analytics report. In dev, `CELERY_TASK_ALWAYS_EAGER=True`.
- **Status caveat:** everything above has been exercised against **dev**
  settings; the production path (`prod.py`, real SMTP/reCAPTCHA/S3,
  `collectstatic`) has not been fully run. `EventMailerTask` async delivery is
  partially wired — see the TODO in `apps/notifications/tasks.py`.

---

*Made with [Claude Code](https://claude.com/claude-code).*
