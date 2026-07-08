"""Add (or fix) a chapter leader with a claim-by-reset account.

Creates the user with an UNUSABLE password (so the only way in is the
password-reset claim flow or Google sign-in), a VERIFIED primary email
(required before allauth will let a privileged user set up 2FA — otherwise the
2FA page reports "account not verified" with no way forward), CoC acceptance,
and an active ChapterLead row. Idempotent: re-running fixes an existing
account (e.g. marks its email verified).

Run:
  python manage.py add_leader <email> --name "Full Name" [--chapter Bangalore] [--send-reset]
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create/fix a chapter leader account (verified email, unusable password, leader role)."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--name", default="")
        parser.add_argument("--chapter", default="Bangalore")
        parser.add_argument("--send-reset", action="store_true", help="email a password-reset (claim) link")

    def handle(self, *args, **opts):
        from allauth.account.models import EmailAddress

        from apps.accounts.models import User
        from apps.chapters.models import Chapter, ChapterLead

        chapter = Chapter.objects.filter(name=opts["chapter"]).first()
        if not chapter:
            self.stderr.write(self.style.ERROR(f"No '{opts['chapter']}' chapter."))
            return

        email = opts["email"].strip().lower()
        user, created = User.objects.get_or_create(email=email, defaults={"name": opts["name"], "is_active": True})
        if opts["name"]:
            user.name = opts["name"]
        user.is_active = True
        if not user.has_usable_password():
            pass  # keep unusable so claim flow is required
        else:
            user.set_unusable_password()
        user.save()
        if hasattr(user, "acknowledge_coc"):
            user.acknowledge_coc()

        # Verified + primary email so 2FA setup is allowed. Demote any other
        # primary flags first so there is exactly one primary.
        EmailAddress.objects.filter(user=user).exclude(email__iexact=email).update(primary=False)
        ea, _ = EmailAddress.objects.get_or_create(user=user, email=email)
        ea.verified = True
        ea.primary = True
        ea.save()

        cl, cl_new = ChapterLead.objects.get_or_create(user=user, chapter=chapter, defaults={"active": True})
        cl.active = True
        cl.save()

        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Updated'} leader {email} ({user.name}) for {chapter.name}; "
            f"email verified, leader={user.is_leader()}."
        ))

        if opts["send_reset"]:
            self._send_reset(chapter, email)

    def _send_reset(self, chapter, email):
        from django.test import RequestFactory

        from allauth.account.forms import ResetPasswordForm

        host = f"{chapter.subdomain}.{__import__('django.conf', fromlist=['settings']).settings.ROOT_DOMAIN}"
        req = RequestFactory().post("/accounts/password/reset/", HTTP_HOST=host, secure=True)
        req.META["HTTP_X_FORWARDED_PROTO"] = "https"
        from django.contrib.sessions.backends.db import SessionStore

        req.session = SessionStore()
        form = ResetPasswordForm({"email": email})
        if form.is_valid():
            form.save(req)
            self.stdout.write(self.style.SUCCESS(f"  reset (claim) email sent to {email}"))
        else:
            self.stderr.write(self.style.WARNING(f"  reset not sent: {form.errors}"))
