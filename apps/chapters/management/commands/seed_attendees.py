"""Seed realistic attendee RSVPs onto Bangalore events — EMAIL-SILENT.

Explicitly sends NO email and NO webhook: registrations are created directly
via the ORM (the RSVP confirmation email lives only in the web view path, not
model.save()), and the registration webhook signal is disconnected for the
duration. Attendee accounts use non-deliverable @seed.invalid addresses so
nothing could reach a real inbox even if a send were triggered.

Populates:
  * the upcoming July 2026 flagship with confirmed RSVPs (drives the
    registration list + check-in dashboard demo)
  * recent past events with a mix of confirmed / absent (drives archive
    attendance + the analytics funnel)

Run: python manage.py seed_attendees [--pool 60] [--per-event 35]
"""

from django.core.management.base import BaseCommand
from django.db.models.signals import post_save


class Command(BaseCommand):
    help = "Seed attendee RSVPs onto Bangalore events (no emails, no webhooks)."

    def add_arguments(self, parser):
        parser.add_argument("--pool", type=int, default=60, help="number of attendee accounts to use")
        parser.add_argument("--per-event", type=int, default=35, help="max RSVPs per event")

    def handle(self, *args, **opts):
        from django.utils import timezone

        from allauth.account.models import EmailAddress
        from apps.accounts.models import User
        from apps.chapters.models import Chapter
        from apps.events.models import Event, EventRegistration
        from apps.notifications import signals as notif

        chapter = Chapter.objects.filter(name="Bangalore").first()
        if not chapter:
            self.stderr.write(self.style.ERROR("No 'Bangalore' chapter."))
            return

        # --- build a stable pool of NON-DELIVERABLE attendee accounts ---
        pool = []
        for i in range(1, opts["pool"] + 1):
            email = f"attendee{i:03d}@seed.invalid"  # RFC 6761 reserved -> never delivered
            u, created = User.objects.get_or_create(
                email=email, defaults={"name": f"null Attendee {i:03d}", "is_active": True}
            )
            if created:
                u.set_unusable_password()
                u.save()
                # verified so these never trigger a verification prompt anywhere
                EmailAddress.objects.get_or_create(
                    user=u, email=email, defaults={"verified": True, "primary": True}
                )
            pool.append(u)

        now = timezone.now()
        # target events: the upcoming flagship + the most recent past events
        upcoming = list(Event.objects.future_public_events().filter(chapter=chapter))
        recent_past = list(
            Event.objects.public_events()
            .filter(chapter=chapter, start_time__lt=now)
            .order_by("-start_time")[:25]
        )
        targets = upcoming + recent_past

        # disconnect webhook + admin-notify (belt-and-suspenders; registration
        # create fires the registration webhook, not these, but be safe)
        try:
            from apps.events.models import EventRegistration as _ER

            post_save.disconnect(dispatch_uid="registration-webhooks", sender=_ER)
        except Exception:
            pass

        created_total = 0
        for idx, event in enumerate(targets):
            # deterministic rotating slice of the pool (no RNG -> idempotent-ish)
            count = min(opts["per_event"], len(pool))
            start = (idx * 7) % len(pool)
            attendees = [pool[(start + j) % len(pool)] for j in range(count)]
            is_past = event.start_time < now
            for j, user in enumerate(attendees):
                reg, was_new = EventRegistration.objects.get_or_create(event=event, user=user)
                if not was_new:
                    continue
                # Past events: mostly attended (checked in), a few no-shows.
                # Upcoming: all confirmed (ready for the check-in demo).
                if is_past:
                    if j % 6 == 0:
                        reg.state = EventRegistration.STATE_ABSENT
                    else:
                        reg.state = EventRegistration.STATE_CONFIRMED
                        reg.checked_in_at = event.start_time
                else:
                    reg.state = EventRegistration.STATE_CONFIRMED
                reg.save(update_fields=["state", "checked_in_at", "updated_at"])
                created_total += 1

        # reconnect the webhook signal
        try:
            notif.connect_registration_webhooks()
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {created_total} attendee RSVPs across {len(targets)} events "
            f"(pool of {len(pool)}). No emails or webhooks were sent."
        ))
