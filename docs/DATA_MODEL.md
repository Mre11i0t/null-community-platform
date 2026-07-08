# Data Model

Core domain models for the null community platform (a multi-tenant Django rewrite of the Rails "swachalit" app). Every model listed here is defined in one of four apps — `apps/chapters`, `apps/events`, `apps/accounts`, `apps/proposals` — on top of two abstract bases in `apps/core/models.py`. Field-level notes below cover only the load-bearing columns; timestamps and boilerplate are omitted.

## Abstract bases (`apps/core/models.py`)

| Base | Provides | Notes |
| --- | --- | --- |
| `TimeStampedModel` | `created_at` (`auto_now_add`), `updated_at` (`auto_now`) | Abstract; on every table (mirrors the original Rails tables). |
| `SoftDeleteModel` | `deleted_at` (nullable), `is_deleted` property, `soft_delete()`, `restore()` | Archive-instead-of-delete. The **default manager still returns archived rows** (admin needs them), so public querysets must go through `.alive()`. |
| `SoftDeleteQuerySet` | `.alive()` / `.deleted()` filters | Attached as the manager on soft-deletable models. |

`apps/core/models.py` also holds `IncidentReport` (Code-of-Conduct triage, admin-only, no public views).

## Relationship overview

```
Chapter 1───* Venue
Chapter 1───* Event ───* EventSession ───* SessionVote / EventSessionComment / StarredSession / SessionQuestion
Chapter 1───* ChapterLead *───1 User            Event ───* EventRegistration *───1 User
Chapter 1───* SessionProposal *───1 User        Event ───* EventFeedback / EventComment / EventPhoto
Chapter 1───* SessionRequest *───1 User         EventType 1───* Event
EventType 1───* SessionProposal                 SessionProposal ───* ProposalReview *───1 User (reviewer)
User (AUTH_USER_MODEL) 1───* UserAuthProfile / UserApiToken / CocAcknowledgement / UserAchievement
EventSession 1 primary speaker (User) + M2M co_speakers (User)
```

- **`Chapter`** is the tenant root: it owns `Venue`s and `Event`s, is served on its own `subdomain`/`custom_domain`, and is administered through `ChapterLead` rows.
- **`Event`** is the central entity — it belongs to a `Chapter`, a `Venue`, and an `EventType`, and fans out to sessions, registrations, feedback, comments, and photos. It is soft-deletable and carries a notification state machine plus Rev-3 check-in / waitlist / custom-question fields.
- **`User`** (custom, email-as-username) is `settings.AUTH_USER_MODEL` and is referenced by nearly every other table.
- Most protective FKs use `on_delete=PROTECT` (Chapter/Venue/EventType on Event); user-owned child rows use `CASCADE`.

---

## Chapter (`apps/chapters/models.py`, table `chapters`)

`TimeStampedModel`. The tenant root. On `save()`, `subdomain` defaults to `slugify(name)` and `custom_domain` is lowercased/stripped.

| Field | Purpose |
| --- | --- |
| `name` | Unique chapter name; drives the default subdomain. |
| `code` | Short chapter code. |
| `subdomain` | `SlugField` (max 63), unique, nullable. Chapter is served at `<subdomain>.<ROOT_DOMAIN>`. Hostname only, lowercase. |
| `custom_domain` | Optional unique apex domain the chapter CNAMEs/ALIASes at the platform. Hostname only. |
| `latitude` / `longitude` | `DecimalField(9,6)`, nullable. Geo pin for the root directory map; filled by the `geocode_chapters` management command. No coords → not plotted. |
| `city` / `state` / `country` | Location text. |
| `active` | Whether the chapter is live (`active_chapters()` classmethod filters on it). |
| `chapter_email`, `image`, `twitter_handle`, `facebook_profile`, `linkedin_profile`, `slideshare_profile`, `github_profile` | Contact + socials. |

Key methods: `site_url()` (custom domain wins over subdomain; scheme/port from `SITE_BASE_URL`), `leads()`, `upcoming_events()` / `past_events()`, `upcoming_events_ics()` (feeds `/chapters/<id>/calendar.ics`).

## ChapterLead (`apps/chapters/models.py`, table `chapter_leads`)

`TimeStampedModel`. Join table making a `User` a leader of a `Chapter`.

| Field | Purpose |
| --- | --- |
| `user` → `User` (CASCADE) | The leader. |
| `chapter` → `Chapter` (CASCADE) | The chapter led. |
| `active` | Only active rows count as leadership (`Chapter.leads()`, `User.is_leader()`). |

Unique constraint on `(user, chapter)`.

---

## Venue (`apps/events/models.py`, table `venues`)

`TimeStampedModel` + `SoftDeleteModel`; manager `SoftDeleteQuerySet`.

| Field | Purpose |
| --- | --- |
| `chapter` → `Chapter` (PROTECT) | Owning chapter. |
| `name`, `address`, `description` | Location details. |
| `map_url`, `map_embedd_code` | External map link / embed HTML. |
| `contact_name`, `contact_email`, `contact_mobile`, `contact_notes` | Venue contact. |

## EventType (`apps/events/models.py`, table `event_types`)

`TimeStampedModel` (not soft-deletable).

| Field | Purpose |
| --- | --- |
| `name` | Unique type name. |
| `max_participant` | Default capacity ceiling (default 10000). |
| `public` | Nullable public flag. |
| `registration_required` | Whether RSVP is needed. |
| `invitation_required` | When true, events of this type are **invite-only** — registrations start `Provisional` pending lead approval (`Event.invite_only()`). |

## Event (`apps/events/models.py`, table `events`)

`TimeStampedModel` + `SoftDeleteModel`; manager `EventQuerySet` (adds `future_events()`, `future_public_events()`, `public_events()`, `archives()` — all go through `.alive()`). On `save()`, `slug` defaults to `slugify(name)`.

| Field | Purpose |
| --- | --- |
| `name`, `description`, `slug`, `image` | Basic event content. |
| `chapter` → `Chapter` (PROTECT) | Owning chapter. |
| `venue` → `Venue` (PROTECT) | Where it happens. |
| `event_type` → `EventType` (PROTECT) | Type; determines invite-only behaviour. |
| `public`, `can_show_on_homepage`, `can_show_on_archive` | Visibility flags (nullable `public`). |
| `accepting_registration` | Master RSVP switch. |
| `state` | Free-text lifecycle field (distinct from `notification_state`). |
| `start_time` / `end_time` | Event window. |
| `registration_start_time` / `registration_end_time` / `registration_instructions` | RSVP window + instructions; `registration_active()` checks now is inside the window. |
| `max_registration` | Seat cap (0 = unlimited). `active_registration_count()` counts only Provisional + Confirmed. |
| `ready_for_announcement`, `announced_at`, `ready_for_notifications`, `notifications_sent_at`, `ready_for_reminders` | Announcement/notification gating flags. |
| `notification_state` | **State machine** (choices): `Init` → `InitialNotifications` → `Reminder1` → `Reminder2` → `PresentationUpdate` → `Finished`. Driven by Celery tasks (`apps/notifications`). |
| `calendar_event_id` | External calendar id. |
| **`check_in_enabled`** (Rev 3) | Per-event; surfaces QR codes / scanner / kiosk / dashboard. Default off. |
| **`auto_absent_enabled`** / `auto_absent_processed_at` (Rev 3) | Lets the post-event sweep mark no-shows `Absent`; timestamp is the sweep idempotency marker. |
| **`custom_questions`** (Rev 3) | `JSONField` list of `{"label": str, "required": bool}` — lead-defined extra RSVP questions. |
| **`cancellation_deadline_hours`** (Rev 3) | Hours before start after which a cancellation counts as a no-show (`Absent`). 0 = cancel anytime; `cancellation_deadline()` computes the cutoff. |
| `feedback_requested_at` (Rev 3) | Set once the post-event feedback email goes out (idempotency). |

Capacity / waitlist logic: `registration_allowed()` compares the cap to `active_registration_count()`; `promote_from_waitlist()` fills freed seats FIFO from `Waitlisted` registrations, flips them to `Confirmed`, and emails each promoted member. Called after any seat-freeing transition.

## EventSession (`apps/events/models.py`, table `event_sessions`)

`TimeStampedModel` + `SoftDeleteModel`; manager `SoftDeleteQuerySet`. A talk/session within an event. `EDIT_WINDOW_DAYS = 30`.

| Field | Purpose |
| --- | --- |
| `event` → `Event` (CASCADE) | Parent event. |
| `user` → `User` (CASCADE) | **Primary speaker.** |
| `co_speakers` M2M → `User` (Rev 3) | Additional credited speakers (`all_speakers()` returns primary first). |
| `speaker_confirmed_at` (Rev 3) | Speaker's explicit "yes, I'll be there"; unconfirmed slots are flagged to leads. Set by `confirm_speaker()`. |
| `name`, `session_type`, `description`, `tags` (taggit) | Session content. |
| `need_projector` / `need_microphone` / `need_whiteboard` | AV requirements. |
| `start_time` / `end_time` | Session slot. |
| `slug`, `presentation_url`, `video_url`, `image` | Links/assets. |
| `placeholder` | Marks a stub (non-placeholder rows are the speaker's real talks). |

`is_editable()` allows edits up to 30 days after `event.end_time`. Voting via related `SessionVote` (`likes_count()` / `dislikes_count()`).

Related session models: `SessionVote` (table `event_session_votes`, one `is_upvote` row per `(session, user)`, first-party replacement for acts_as_votable), `EventSessionComment`, `StarredSession` (personal agenda, unique per `(user, session)`), `SessionQuestion` (live Q&A with `upvoters` M2M and `is_hidden`).

## EventRegistration (`apps/events/models.py`, table `event_registrations`)

`TimeStampedModel` (not soft-deletable); manager `EventRegistrationQuerySet` (adds `.absent()`). Unique on `(event, user)`.

**States:** `Provisional`, `Confirmed`, `Not Attending`, `Absent`, `Waitlisted` (Rev 3). Seat-holding states are `Provisional` + `Confirmed`.

| Field | Purpose |
| --- | --- |
| `event` → `Event` (CASCADE) | Event being registered for. |
| `user` → `User` (CASCADE) | The registrant. |
| `state` | One of the five states above. |
| `visible`, `accepted` | Legacy visibility / lead-acceptance flags (`accepted` nullable). |
| **`check_in_code`** (Rev 3) | Opaque unique per-registration code, rendered as a QR. Auto-generated (`secrets.token_urlsafe(16)`) on save. |
| **`checked_in_at`** (Rev 3) | When attendance was recorded at the door; `check_in()` sets it and forces `Confirmed`. |
| **`custom_answers`** (Rev 3) | `JSONField` `{label: answer}` for the event's custom questions. |
| `review_note` (Rev 3) | Lead's note from the approval queue. |

Behaviour: `save()` sets the default state on create — `Waitlisted` if the event is full, else `Provisional` for invite-only events, else `Confirmed`. `clean()` blocks new RSVPs when registration is inactive or the user is `rsvp_blocked()` (too many recent no-shows); a full event waitlists rather than rejects. `set_state()` transitions state and triggers `promote_from_waitlist()` when a seat is freed. `waitlist_position()` returns FIFO rank.

Other Event children: `EventFeedback` (1–5 `rating`, unique per `(event, user)`), `EventComment`, `EventPhoto`.

---

## User (`apps/accounts/models.py`, table `users`)

`AbstractBaseUser` + `PermissionsMixin` + `TimeStampedModel`. This is `settings.AUTH_USER_MODEL`. Custom `UserManager`; **`USERNAME_FIELD = "email"`** (email-as-username), `REQUIRED_FIELDS = []`. Devise auth fields are replaced by Django auth + django-allauth.

| Field | Purpose |
| --- | --- |
| `email` | Unique; the login identifier. |
| `name`, `handle`, `about_me`, `homepage`, `avatar` | Profile. |
| `twitter_handle`, `facebook_profile`, `linkedin_profile`, `slideshare_profile`, `github_profile` | Socials. |
| `is_active`, `is_staff` | Standard auth flags (superuser via `PermissionsMixin`). |

Notable methods: `is_leader()` / `managed_chapters()` / `managed_events()` (via `ChapterLead`); no-show enforcement `no_show_strikes()` (Absent regs inside `NO_SHOW_WINDOW_DAYS`) and `rsvp_blocked()` (≥ `NO_SHOW_STRIKE_LIMIT`); **Code of Conduct** `has_acknowledged_coc()` / `acknowledge_coc()` (checks `COC_VERSION`); and `anonymize_and_deactivate()` (Rev 3 self-service deletion — scrubs PII, purges tokens and allauth `EmailAddress` rows, keeps history rows pointing at an anonymized shell).

Account-related models:

| Model / table | Purpose |
| --- | --- |
| `UserAuthProfile` (`user_auth_profiles`) | OAuth identity (`uid`, `provider`, binary `oauth_data`/`extra`). |
| `UserApiToken` (`user_api_tokens`) | API tokens; auto-generated (`token_urlsafe(48)`), 24h default expiry, `active` flag; `create_for_request()` captures UA/IP. |
| `CocAcknowledgement` (`coc_acknowledgements`) | One row per `(user, version)` CoC acceptance; versioned so a policy update re-prompts. Unique per version. |

---

## SessionProposal (`apps/proposals/models.py`, table `session_proposals`)

`TimeStampedModel`. A member proposing a topic to a chapter (the CFP pipeline). Chapter leads are emailed on creation (`apps/proposals/signals.py`).

**CFP states (`status`):** `submitted` → `under_review` → `accepted` / `rejected` / `waitlisted` → `scheduled` (default `submitted`).

| Field | Purpose |
| --- | --- |
| `chapter` → `Chapter` (CASCADE) | Target chapter. |
| `user` → `User` (CASCADE) | Proposer. |
| `event_type` → `EventType` (CASCADE) | Proposed format. |
| `session_topic`, `session_description` | The pitch. |
| `status` | Pipeline stage (choices above). |

`set_status(new_status, note="")` transitions the pipeline and **emails the proposer** on every change (Rev 3 gap #6 — the original submitted into a void). `average_score()` aggregates related `ProposalReview.score`.

Related proposal models: `ProposalReview` (table `proposal_reviews`, one 1–5 `score` + comment per reviewer, unique per `(proposal, reviewer)`), `SessionRequest` (community-suggested topic for a chapter), `UserAchievement` (member achievements: Bug Discovery / Bug Bounty / Open Source / Community Support, self- or null-sourced, unique per `(user, reference)`).

---

*Made with [Claude Code](https://claude.com/claude-code).*
