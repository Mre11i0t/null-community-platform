"""Seed the Bangalore chapter with the real null Bangalore history.

Reads the local SQLite workspace DB (attendees.db: null_events +
null_event_sessions, scraped from null.community) and imports:
  * 227 past events  -> Bangalore archive + stats
  * 1191 talk sessions -> searchable session archive

The source has no speaker<->session links and no venue names, so imported
sessions are attributed to a shared "null Bangalore (archive)" speaker account
and events use a single archive venue. Real named speakers live on the July
2026 event seeded separately (import_july2026).

Signals are disconnected during import: otherwise each of 227 event creates
would fire notify_admin_on_create + webhook_on_publish, blasting hundreds of
Mailgun emails/webhooks under eager Celery.

Run: python manage.py import_bangalore --db "/path/to/attendees.db" [--limit N]
"""

import sqlite3

from django.core.management.base import BaseCommand
from django.db.models.signals import post_save
from django.utils.dateparse import parse_datetime

from apps.chapters.models import Chapter


class Command(BaseCommand):
    help = "Import real null Bangalore events + sessions from the attendees.db SQLite workspace."

    def add_arguments(self, parser):
        parser.add_argument("--db", required=True, help="path to attendees.db")
        parser.add_argument("--limit", type=int, default=0, help="cap events imported (0 = all)")

    def handle(self, *args, **opts):
        from apps.accounts.models import User
        from apps.events.models import Event, EventSession, EventType, Venue
        from apps.notifications import signals as notif

        chapter = Chapter.objects.filter(name="Bangalore").first()
        if not chapter:
            self.stderr.write(self.style.ERROR("No 'Bangalore' chapter — seed it first."))
            return

        # --- suppress the notification/webhook side effects during bulk import ---
        post_save.disconnect(notif.notify_admin_on_create, sender=Event)
        post_save.disconnect(notif.webhook_on_publish, sender=Event)
        try:
            self._run(opts, chapter, User, Event, EventSession, EventType, Venue)
        finally:
            post_save.connect(notif.notify_admin_on_create, sender=Event)
            post_save.connect(notif.webhook_on_publish, sender=Event)

    def _run(self, opts, chapter, User, Event, EventSession, EventType, Venue):
        etype, _ = EventType.objects.get_or_create(
            name="Monthly Meet", defaults={"description": "Regular monthly meetup", "public": True}
        )
        venue, _ = Venue.objects.get_or_create(
            chapter=chapter,
            name="null Bangalore (archive)",
            defaults={"address": "Bangalore, India", "contact_name": "null Bangalore"},
        )
        archivist, _ = User.objects.get_or_create(
            email="archive@bangalore.null.community",
            defaults={"name": "null Bangalore (archive)", "is_active": True},
        )
        if archivist.has_usable_password() is False:
            pass
        else:
            archivist.set_unusable_password()
            archivist.save()

        con = sqlite3.connect(opts["db"])
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM null_events ORDER BY start_time").fetchall()
        if opts["limit"]:
            rows = rows[: opts["limit"]]

        ev_created = sess_created = 0
        for r in rows:
            start = parse_datetime(r["start_time"] or "")
            end = parse_datetime(r["end_time"] or "") or start
            if not start:
                continue
            name = (r["name"] or "").strip() or f"null Bangalore Meet {start.date()}"
            event, was_new = Event.objects.get_or_create(
                chapter=chapter,
                name=name,
                start_time=start,
                defaults={
                    "venue": venue,
                    "event_type": etype,
                    "description": (r["description"] or "").strip(),
                    "end_time": end,
                    "public": True,
                    "can_show_on_archive": True,
                    "can_show_on_homepage": True,
                    "notification_state": Event.STATE_FINISHED,
                },
            )
            if was_new:
                ev_created += 1
            # sessions for this event
            srows = con.execute(
                "SELECT * FROM null_event_sessions WHERE null_event_id = ?", (r["null_event_id"],)
            ).fetchall()
            for s in srows:
                sname = (s["name"] or "").strip()
                if not sname:
                    continue
                s_start = parse_datetime(s["start_time"] or "") or start
                s_end = parse_datetime(s["end_time"] or "") or s_start
                sess, s_new = EventSession.objects.get_or_create(
                    event=event,
                    name=sname[:255],
                    defaults={
                        "user": archivist,
                        "description": (s["description"] or "").strip(),
                        "session_type": (s["session_type"] or "").strip()[:255],
                        "presentation_url": (s["presentation_url"] or "").strip()[:255],
                        "video_url": (s["video_url"] or "").strip()[:255],
                        "start_time": s_start,
                        "end_time": s_end,
                    },
                )
                if s_new:
                    sess_created += 1
                    tags = [t.strip() for t in (s["tags"] or "").split(",") if t.strip()]
                    if tags:
                        sess.tags.add(*tags[:8])
        con.close()
        self.stdout.write(self.style.SUCCESS(f"Imported {ev_created} events, {sess_created} sessions into Bangalore."))
