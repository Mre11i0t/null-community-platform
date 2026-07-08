"""Seed the upcoming July 2026 null/OWASP Bangalore flagship meetup.

Talk titles + abstracts are the real confirmed agenda (from the speakers'
coordination). Sessions are attributed to a community speaker account rather
than inventing individual identities. The event is public + accepting
registrations + check-in enabled, so it drives the RSVP/check-in demo.

Run: python manage.py import_july2026
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models.signals import post_save
from django.utils import timezone

from apps.chapters.models import Chapter

TALKS = [
    ("Anatomy of Attack Vectors and Firmware Security Below the OS",
     "Explores attack vectors targeting firmware below the OS — BIOS, UEFI and hardware "
     "initialisation, the boot process, and how attackers exploit firmware for persistent, "
     "stealthy access that bypasses traditional security controls.",
     ["firmware", "uefi", "bios"]),
    ("It's Just Data..., Until It Isn't: The Grammar of Injection Attacks",
     "In modern web apps user input is everywhere and usually treated as harmless data. But "
     "what happens when that data is interpreted as code? A fundamentals-first look at the "
     "grammar behind injection attacks.",
     ["injection", "web", "appsec"]),
    ("Beyond the Breach: Architecting Resilience through Structured Incident Response",
     "In the wake of the 2024 Ticketmaster breach that exposed 560M customers, a reminder that "
     "technical debt and missing MFA are not just IT issues. Architecting resilience through "
     "structured incident response.",
     ["incident-response", "blueteam"]),
    ("GenAI vs. IEC 62443: Are Our OT Security Levels Still Enough?",
     "How GenAI is democratising the expertise needed to attack ICS/OT systems, and what that "
     "means for IEC/ISA 62443 security levels.",
     ["ot", "ics", "genai"]),
    ("When RBAC isn't enough: Exploiting Kubernetes nodes/proxy for RCE",
     "Going past Kubernetes RBAC — abusing the nodes/proxy subresource to reach remote code "
     "execution on cluster nodes.",
     ["kubernetes", "cloud", "rce"]),
    ("DLLs: Intended Feature, Unintended Abuse",
     "How a legitimate Windows feature — dynamic-link libraries — becomes an attacker's "
     "playground: search-order hijacking, sideloading and proxying.",
     ["windows", "malware", "redteam"]),
    ("TOR Beyond Crime: How Professionals Use Onion Routing for Real Security",
     "Onion routing past its reputation — how security professionals use Tor for legitimate "
     "privacy, research and operational security.",
     ["privacy", "tor", "opsec"]),
    ("Malvertising Beyond the Ad",
     "The malvertising kill chain past the ad impression — redirect infrastructure, payload "
     "delivery and the abuse of legitimate ad networks.",
     ["malware", "threat-intel"]),
    ("Getting Started with Threat Hunting in ELK",
     "A practical on-ramp to threat hunting with the ELK stack — data sources, detections and "
     "hunting lateral movement.",
     ["threat-hunting", "elk", "blueteam"]),
    ("Privacy Landscape Worldwide & Personal Data Protection",
     "A tour of the global privacy landscape and personal data protection — DPDP, GDPR and what "
     "practitioners need to know.",
     ["privacy", "dpdp", "compliance"]),
    ("Privacy Risk Management for Generative & Agentic AI with PETs",
     "Privacy-enhancing technologies for GenAI and agentic AI systems — addressing data leakage, "
     "inference attacks and autonomous-agent risk.",
     ["ai", "privacy", "pets"]),
]


class Command(BaseCommand):
    help = "Seed the upcoming July 2026 null/OWASP Bangalore flagship meetup with its real agenda."

    def handle(self, *args, **opts):
        from apps.accounts.models import User
        from apps.events.models import Event, EventSession, EventType, Venue
        from apps.notifications import signals as notif

        chapter = Chapter.objects.filter(name="Bangalore").first()
        if not chapter:
            self.stderr.write(self.style.ERROR("No 'Bangalore' chapter."))
            return

        etype, _ = EventType.objects.get_or_create(
            name="Monthly Meet", defaults={"description": "Regular monthly meetup", "public": True}
        )
        venue, _ = Venue.objects.get_or_create(
            chapter=chapter,
            name="null/OWASP Bangalore Venue",
            defaults={"address": "Bangalore, India", "contact_name": "null Bangalore"},
        )
        speaker, _ = User.objects.get_or_create(
            email="speakers@bangalore.null.community",
            defaults={"name": "null/OWASP Bangalore Speakers", "is_active": True},
        )

        # Late-July 2026, upcoming relative to the seeded 'today'.
        start = timezone.now() + timedelta(days=17)
        start = start.replace(hour=9, minute=30, second=0, microsecond=0)
        end = start.replace(hour=17)

        post_save.disconnect(notif.notify_admin_on_create, sender=Event)
        post_save.disconnect(notif.webhook_on_publish, sender=Event)
        try:
            event, _ = Event.objects.get_or_create(
                chapter=chapter,
                name="null/OWASP Bangalore — July 2026 Meetup",
                defaults={
                    "venue": venue,
                    "event_type": etype,
                    "description": (
                        "The flagship monthly null Bangalore meetup, co-hosted with OWASP Bangalore. "
                        "A full day of talks across firmware security, AppSec, cloud, AI privacy, "
                        "threat hunting and incident response. RSVP to reserve your seat — on-site "
                        "check-in is enabled."
                    ),
                    "start_time": start,
                    "end_time": end,
                    "registration_start_time": timezone.now() - timedelta(days=1),
                    "registration_end_time": start - timedelta(hours=2),
                    "public": True,
                    "accepting_registration": True,
                    "can_show_on_homepage": True,
                    "check_in_enabled": True,
                    "max_registration": 120,
                },
            )
            for i, (title, abstract, tags) in enumerate(TALKS):
                s, new = EventSession.objects.get_or_create(
                    event=event,
                    name=title[:255],
                    defaults={
                        "user": speaker,
                        "description": abstract,
                        "start_time": start + timedelta(minutes=30 * (i + 1)),
                        "end_time": start + timedelta(minutes=30 * (i + 1) + 25),
                    },
                )
                if new and tags:
                    s.tags.add(*tags)
        finally:
            post_save.connect(notif.notify_admin_on_create, sender=Event)
            post_save.connect(notif.webhook_on_publish, sender=Event)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded '{event.name}' on {start.date()} with {len(TALKS)} sessions."
        ))
