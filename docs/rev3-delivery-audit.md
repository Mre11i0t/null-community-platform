# Rev 3 Delivery Verification — Audit & Fixes

**Date:** 2026-07-08
**Branch:** `audit/rev3-delivery-verification`
**Method:** Adversarial multi-agent audit (37 agents) of the PRD's Part 9
"✅ DELIVERED" claim, cross-checked against the actual code and tests.
Auditors traced the real code path for each claimed feature and *read*
(did not run) the tests to judge whether each one exercises the real path
or is a shallow status check. Every non-CONFIRMED verdict was then handed
to a second agent tasked with *refuting* it, to avoid "fixing" things that
already work.

## Bottom line

The "DELIVERED" claim is **substantially true.** Across 16 audit units and
72 individually-verified feature claims:

| Verdict | Count |
|---|---|
| CONFIRMED (works end-to-end, real-path test) | 55 |
| PARTIAL | 15 |
| MISSING | 1 |
| BROKEN | 1 |

Of the 17 non-CONFIRMED claims, adversarial verification found **9 genuine
gaps** in claimed-delivered features. **6 were clean, self-contained bugs
or omissions — all 6 are now fixed with tests** (this branch). The other 3
are intentionally *not* built autonomously (reasons below). The remaining 8
non-CONFIRMED claims are not real gaps — they are credential-gated by design
or the first-pass auditor was over-strict and the feature actually works.

Test suite: **198 → 202 passing** (4 new real-path tests; 2 existing tests
tightened to assert the corrected behavior).

**Assurance boundary (read this).** The adversarial refute-pass was applied
only to the 17 non-CONFIRMED claims — that is where the gap-hunting effort
went. The **55 CONFIRMED verdicts were single-pass**: one auditor read the
implementing code and its test and judged the test exercises the real path,
but none were sent to a second agent to refute. So "DELIVERED is
substantially true" rests on trust in those 55, and the one class this audit
did *not* re-check is a **false-CONFIRMED** — a feature that looks built with
a test too shallow to catch a latent bug. If you want a stronger guarantee,
the next pass would adversarially re-verify the 55 CONFIRMEDs (especially the
HIGH-traffic member/leader flows).

---

## ✅ Fixed on this branch (6)

Commit `8a416fc`. Each fix ships with a test that hits the real path — the
198-test suite was green *while these were broken*, so passing tests alone
could not catch them.

| # | Sev | Feature | Defect | Fix |
|---|-----|---------|--------|-----|
| 1 | **HIGH** | Mailgun/Anymail email backend env-gating (PRD Part 6) | `config/settings/base.py:279` set the anymail backend inside `if MAILGUN_API_KEY:`, but `base.py:338` then **unconditionally** reassigned `EMAIL_BACKEND` to SMTP later in the same module. So `MAILGUN_API_KEY` was **dead in prod** — the anymail line never took effect. dev/test override `EMAIL_BACKEND` after base, which masked the bug. | Guard the SMTP fallback behind `if not MAILGUN_API_KEY`. |
| 2 | MED | Registration confirmation email (PRD Part 7 + 3.7) | `registration_new` sent **no email at all** on RSVP; `templates/emails/` was empty. The check-in QR only existed on the RSVP page, never "in the confirmation email" as claimed. | Send a confirmation email on a confirmed RSVP; when the event opts into check-in it carries the check-in code + QR-pass link. New template `templates/events/emails/registration_confirmation.txt`. |
| 3 | MED | `can_show_on_homepage` flag | Field was editable by leads (`leads/forms.py`) and admins, but **consumed by zero queries** — unchecking "show on homepage" did nothing; the event still rendered. (`can_show_on_archive`, its twin, *was* honored.) | Honor `can_show_on_homepage=True` in the chapter `home()` view. |
| 4 | LOW | Notification state machine → Finished | Machine advanced `Init → … → PresentationUpdate` and **stalled there forever**; `STATE_FINISHED` was defined but never assigned. | Add the terminal `PresentationUpdate → Finished` sweep (after the ~7-day presentation-upload window). |
| 5 | LOW | Per-event OG cards (SEO) | `og:image`, `og:url`, `twitter:image` were absent everywhere despite `Event.image_url()` being a ready source; shared event links rendered no preview image. | Emit them from `Event.image_url()`; use a large-image twitter card on event pages. |
| 6 | LOW | `/event/<name>` slug alias (SEO) | Returned **302** (temporary); for canonical link-equity consolidation onto `/events/:id` it should be **301** (permanent). | `permanent=True`. |

---

## ⏸ Genuine gaps intentionally NOT built autonomously (3)

These are real partials, but each needs a product decision or is explicitly
out of the selected scope, so building them unsupervised would be the wrong
call. Flagged for your decision.

- **Timezone: render in *viewer's* timezone** (foundations, LOW). Today the
  app stores UTC and renders **with** an explicit label — but always in the
  single server zone (`Asia/Kolkata`), never the viewer's. Delivering true
  viewer-TZ needs a design choice: a user-profile timezone field vs. a
  JS-detected `tz` cookie + an `activate()` middleware. Pick one and it's a
  ~30-line change (`apps/accounts/models.py` or a middleware +
  `config/settings/base.py`). The explicit label already mitigates the worst
  of it.
- **Gamification: "volunteering" points** (engagement, LOW). Points cover
  attending / speaking / co-speaking, but there is **no volunteer data model
  anywhere** to award volunteering from. This is a new feature (volunteer
  tracking), not a constant — either add an `EventVolunteer` relation or drop
  "volunteering" from the claim.
- **Notification preference center: push channel + digests categories**
  (communications, MED-listed but mostly deferred). The core center (per-
  category **email** toggles + **WhatsApp** opt-in, honored in delivery)
  works. The missing pieces are **web push** and **digests** — both are
  explicitly **Deferred (not selected)** Part-B backlog items, so building
  them would contradict the PRD's own scoping. The category naming also
  differs from the claim (reminders/speaker/feedback vs.
  reminders/announcements/digests) — a copy/scope reconciliation, not code.

---

## ℹ️ Not gaps — credential-gated or by design (as the PRD states)

- **Chapter pin map** on the home/directory (root_directory) — MISSING, but
  the parity matrix already admits "Not ported (needs a Maps API key +
  geocoding)". Credential-gated, documented, intentional.
- **Google/GitHub social login** (platform) — PARTIAL only because it is
  **env-gated**: without OAuth credentials the buttons hide and email/
  password remains. That is the PRD's "absent credentials degrade gracefully"
  contract working as designed, not a defect.
- **Chapter health dashboard, speaker analytics, post-event feedback survey,
  and 3 multi-tenant routing claims** — first-pass auditors rated these
  PARTIAL, but adversarial verification found them actually implemented and
  working (over-strict initial reads). No action needed.

## Confirmed working end-to-end (highlights)

Registration upgrades (waitlist auto-promotion, invite-only approval queue,
custom questions, no-show strikes), the full CFP pipeline (reviewer scoring,
status emails, co-speakers, speaker confirmation), Trust & Safety (versioned
CoC, incident reporting, account anonymization, data export, TOTP 2FA),
personal agenda, check-in/scanner/kiosk/auto-absent, HMAC webhooks, broadcast
channels, soft-delete/restore, per-event ICS, and the API v2 contract — all
CONFIRMED with real-path tests.

---

## Not touched (per plan / product decision)

The deliberately-**Deferred** Part-B backlog (paid ticketing, group/+1,
per-session capacity, printable badges, web push, chapter digests, virtual/
hybrid, recording auto-attach, multi-track agenda, certificates, per-chapter
CMS pages/nav, embeddable widgets, PWA, AI assists) was **not** built — these
are documented product decisions, not gaps.

Everything here is on the `audit/rev3-delivery-verification` branch and has
**not** been pushed or merged. Review the branch diff to accept.
