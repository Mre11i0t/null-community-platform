"""Settings for a next-day showcase running on a Mac Mini behind a
Cloudflare Tunnel (see deploy/showcase/README.md).

Inherits prod (DEBUG=False, secure cookies, WhiteNoise manifest static,
STORAGES, CSRF_TRUSTED_ORIGINS) but adapts the handful of things that
differ when Cloudflare terminates TLS at its edge and forwards plain HTTP
to a local gunicorn:

  * trust the edge's X-Forwarded-Proto so Django knows the request is https
  * don't redirect to https at the origin (the edge already forces it) —
    would otherwise risk a loop
  * don't emit HSTS — a year of forced-https + preload is not something you
    want to pin onto a real domain for a throwaway demo
  * share the session/CSRF cookie across every chapter subdomain so one
    login works on delhi.<domain>, bangalore.<domain>, ... (PRD Part 0)
  * run Celery inline so there's no separate worker/beat to babysit
"""

from .prod import *  # noqa: F401,F403

# Cloudflare Tunnel forwards HTTP to the origin; the edge is HTTPS and sets
# X-Forwarded-Proto. Trust it so request.is_secure() / secure cookies work.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# The Cloudflare edge already forces HTTPS ("Always Use HTTPS"); redirecting
# again at the origin is redundant and loop-prone. Leave it to the edge.
SECURE_SSL_REDIRECT = False

# Do NOT pin HSTS onto a real domain for a demo host.
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# One login across every chapter subdomain. Set SESSION_COOKIE_DOMAIN and
# CSRF_COOKIE_DOMAIN to ".<yourdomain>" (leading dot) in the environment.
SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN", default=None)  # noqa: F405
CSRF_COOKIE_DOMAIN = env("CSRF_COOKIE_DOMAIN", default=SESSION_COOKIE_DOMAIN)  # noqa: F405

# Run notification/email tasks inline — no separate Celery worker or beat to
# keep alive during the demo. Time-based reminders won't fire (they need
# beat), but on-demand mails (RSVP confirmation, announcements) do.
CELERY_TASK_ALWAYS_EAGER = True

# Console email by default (visible in the gunicorn log, nothing to configure).
# Set MAILGUN_API_KEY in the env to send real mail instead.
if not env("MAILGUN_API_KEY", default=""):  # noqa: F405
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Seeded demo users have unverified emails, and there's no real inbox to click
# a confirmation link in (console/sandbox email). base.py mandates verification
# (prod-correct); relax it for the demo so seeded logins work — same reasoning
# as dev.py. Sign-ups during the demo also skip the confirm-email gate.
ACCOUNT_EMAIL_VERIFICATION = "optional"

# Keep the demo frictionless: don't force TOTP enrolment before admins/leads
# can do anything. Flip REQUIRE_2FA_FOR_PRIVILEGED=1 in the env to showcase 2FA.
REQUIRE_2FA_FOR_PRIVILEGED = env.bool("REQUIRE_2FA_FOR_PRIVILEGED", default=False)  # noqa: F405
