"""
Base settings shared by all environments.
Ported from the original Rails app's config/application.rb and config/environments/.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-secret-key-change-me")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    # Third-party
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "taggit",
    "auditlog",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.mfa",
    "django_celery_beat",
    "django_celery_results",
    "crispy_forms",
    "crispy_bootstrap5",
    "django_recaptcha",
    # Local apps — mirror the original Rails models/controllers split
    "apps.core",
    "apps.accounts",
    "apps.chapters",
    "apps.events",
    "apps.content",
    "apps.proposals",
    "apps.notifications",
    "apps.leads",
    "apps.api",
    "apps.analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.chapters.middleware.ChapterSiteMiddleware",
    "apps.accounts.middleware.Privileged2FAMiddleware",
    "apps.analytics.middleware.PageVisitMiddleware",
]

# Chapter-sites architecture (PRD Part 0): hostname whose subdomains are
# chapter sites; the bare domain is the root/directory site. Hostname
# only — no scheme, no port.
ROOT_DOMAIN = env("ROOT_DOMAIN", default="localhost")

# In prod, set SESSION_COOKIE_DOMAIN=.null.community (and the CSRF
# equivalent) so one login works across every chapter subdomain.
SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN", default=None)
CSRF_COOKIE_DOMAIN = env("CSRF_COOKIE_DOMAIN", default=None)

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site_config",
                "apps.core.context_processors.nav_data",
                "apps.chapters.context_processors.current_chapter",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Database — defaults match the original docker-compose MySQL service
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("MYSQL_DATABASE", default="swachalit"),
        "USER": env("MYSQL_USERNAME", default="root"),
        "PASSWORD": env("MYSQL_PASSWORD", default="s0m3p4ssw0rd"),
        "HOST": env("MYSQL_SERVER", default="db"),
        "PORT": env("MYSQL_PORT", default="3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Original Rails app used Asia/Kolkata throughout (config/application.rb)
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Django 5.1 removed STATICFILES_STORAGE / DEFAULT_FILE_STORAGE in favour of
# the STORAGES dict — the old settings are silently IGNORED, so they must
# live here. Dev/test keep the plain backends (no collectstatic manifest to
# resolve); prod.py swaps staticfiles to WhiteNoise's compressed-manifest
# backend and default to S3 when a bucket is configured.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SITE_ID = 1

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# django-allauth — replaces Devise
ACCOUNT_EMAIL_VERIFICATION = "mandatory"  # mirrors Devise :confirmable
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None  # our User has no username field, email-only login
# Legacy-named settings kept in sync with the above for this allauth
# version's system checks, which still read these directly rather than
# deriving them from ACCOUNT_LOGIN_METHODS/ACCOUNT_SIGNUP_FIELDS.
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_FORMS = {"signup": "apps.accounts.forms.CaptchaSignupForm"}
ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/5m",  # mirrors Devise :lockable
}

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.api.authentication.ApiTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticatedOrReadOnly",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "null Community Platform API",
    "DESCRIPTION": "Public API for null.community — events, chapters, sessions.",
    "VERSION": "2.0.0",
}

# Celery — replaces Resque + Resque Scheduler
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_TIMEZONE = TIME_ZONE
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# Periodic sweep replacing Resque Scheduler's one-shot delayed jobs — ports
# Event's notification_state machine (see apps/notifications/tasks.py
# dispatch_event_notifications). Runs every 15 minutes in prod; nothing polls
# this automatically in dev unless celery beat is started separately, so
# during manual testing call the task directly.
CELERY_BEAT_SCHEDULE = {
    "dispatch-event-notifications": {
        "task": "apps.notifications.tasks.dispatch_event_notifications",
        "schedule": 900.0,
    },
    "auto-mark-absent": {
        "task": "apps.events.tasks.auto_mark_absent",
        "schedule": 900.0,
    },
    "send-feedback-requests": {
        "task": "apps.events.tasks.send_feedback_requests",
        "schedule": 1800.0,
    },
    # 1st of every month, 09:00 IST
    "monthly-chapter-reports": {
        "task": "apps.analytics.tasks.send_monthly_chapter_reports",
        "schedule": crontab(minute=0, hour=9, day_of_month=1),
    },
}

# Rev 3 no-show strikes: an Absent registration is a strike; users at or
# over the limit within the rolling window are temporarily blocked from
# RSVPing. Set NO_SHOW_STRIKE_LIMIT=0 to disable blocking entirely.
NO_SHOW_STRIKE_LIMIT = env.int("NO_SHOW_STRIKE_LIMIT", default=3)
NO_SHOW_WINDOW_DAYS = env.int("NO_SHOW_WINDOW_DAYS", default=180)

# Rev 3 trust & safety
COC_VERSION = env("COC_VERSION", default="1.0")
INCIDENT_RESPONSE_ADDRESSES = env.list("INCIDENT_RESPONSE_ADDRESSES", default=["conduct@null.community"])
# When on, chapter leads must have TOTP 2FA to use /leads/, and staff
# to use /admin/. Off by default so dev/test aren't blocked; prod.py
# turns it on.
REQUIRE_2FA_FOR_PRIVILEGED = env.bool("REQUIRE_2FA_FOR_PRIVILEGED", default=False)

# Rev 3 communications
FEEDBACK_DELAY_HOURS = env.int("FEEDBACK_DELAY_HOURS", default=6)
WHATSAPP_API_TOKEN = env("WHATSAPP_API_TOKEN", default="")
WHATSAPP_PHONE_NUMBER_ID = env("WHATSAPP_PHONE_NUMBER_ID", default="")

# Rev 3 social login (closes gap #5): Google/GitHub via allauth, strictly
# env-gated — without credentials the provider apps aren't even installed,
# so no dead buttons and no misconfigured OAuth endpoints.
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")
GITHUB_OAUTH_CLIENT_ID = env("GITHUB_OAUTH_CLIENT_ID", default="")
GITHUB_OAUTH_CLIENT_SECRET = env("GITHUB_OAUTH_CLIENT_SECRET", default="")

SOCIALACCOUNT_PROVIDERS = {}
if GOOGLE_OAUTH_CLIENT_ID:
    INSTALLED_APPS.append("allauth.socialaccount.providers.google")
    SOCIALACCOUNT_PROVIDERS["google"] = {
        "APP": {"client_id": GOOGLE_OAUTH_CLIENT_ID, "secret": GOOGLE_OAUTH_CLIENT_SECRET},
        "SCOPE": ["profile", "email"],
    }
if GITHUB_OAUTH_CLIENT_ID:
    INSTALLED_APPS.append("allauth.socialaccount.providers.github")
    SOCIALACCOUNT_PROVIDERS["github"] = {
        "APP": {"client_id": GITHUB_OAUTH_CLIENT_ID, "secret": GITHUB_OAUTH_CLIENT_SECRET},
        "SCOPE": ["user:email"],
    }

# Trust provider-verified emails: log straight into the matching account
# instead of creating a duplicate.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# Rev 3 email delivery: Mailgun via django-anymail when a key is present
# (Basic $15/mo · 10k emails covers current volume; see PRD Part 6),
# otherwise whatever EMAIL_BACKEND the environment set (console in dev).
# Rev 3: sentry-sdk replaces the deprecated sentry-raven gem — env-gated.
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1, send_default_pii=False)

MAILGUN_API_KEY = env("MAILGUN_API_KEY", default="")
if MAILGUN_API_KEY:
    INSTALLED_APPS.append("anymail")
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
    ANYMAIL = {
        "MAILGUN_API_KEY": MAILGUN_API_KEY,
        "MAILGUN_SENDER_DOMAIN": env("MAILGUN_SENDER_DOMAIN", default="null.community"),
        "MAILGUN_API_URL": env("MAILGUN_API_URL", default="https://api.mailgun.net/v3"),
    }

# Rev 3 broadcast channels (replaces the dead Twitter-via-IFTTT path).
# Free webhook channels first; X API v2 optional and pay-per-use
# ($0.015/post, $0.20 with a link — see PRD Part 6). All env-gated.
DISCORD_WEBHOOK_URL = env("DISCORD_WEBHOOK_URL", default="")
SLACK_WEBHOOK_URL = env("SLACK_WEBHOOK_URL", default="")
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID", default="")
X_CONSUMER_KEY = env("X_CONSUMER_KEY", default="")
X_CONSUMER_SECRET = env("X_CONSUMER_SECRET", default="")
X_ACCESS_TOKEN = env("X_ACCESS_TOKEN", default="")
X_ACCESS_TOKEN_SECRET = env("X_ACCESS_TOKEN_SECRET", default="")

# reCAPTCHA — used on signup, RSVP, and session comments in the original app
RECAPTCHA_PUBLIC_KEY = env("RECAPTCHA_PUBLIC_KEY", default="")
RECAPTCHA_PRIVATE_KEY = env("RECAPTCHA_PRIVATE_KEY", default="")

# Content Security Policy — the original Rails app had no CSP at all
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": [
            "'self'",
            "https://checkout.razorpay.com",
            "https://www.google.com/recaptcha/",
            "https://www.gstatic.com/recaptcha/",
            "'unsafe-inline'",
        ],
        "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "img-src": ["'self'", "data:", "https:"],
        "frame-src": ["'self'", "https://www.google.com/recaptcha/"],
    }
}

# Site-wide config values — mirrors config/misc_config in the original app
CFG_APP_TITLE = env("CFG_APP_TITLE", default="null Community Platform")
CFG_APP_DESCRIPTION = env(
    "CFG_APP_DESCRIPTION",
    default="null is one of the most active, open security communities in India.",
)
CFG_GOOGLE_GROUPS_URL = "https://groups.google.com/forum/#!forum/null-co-in"
CFG_VOLUNTEER_FORM_URL = env("CFG_VOLUNTEER_FORM_URL", default="https://null.community")

# Mirrors CFG_NOTIFICATION_ANNOUNCEMENT_DEFAULT_ADDRESSES / CFG_NOTIFICATION_ADMIN_EVENT_CREATE
NOTIFICATION_ANNOUNCEMENT_ADDRESSES = env.list(
    "NOTIFICATION_ANNOUNCEMENT_ADDRESSES", default=["announce@null.community"]
)
NOTIFICATION_ADMIN_EVENT_CREATE = env.list("NOTIFICATION_ADMIN_EVENT_CREATE", default=["admin@null.community"])

# Used to build absolute URLs inside emails, where there is no request object.
SITE_BASE_URL = env("SITE_BASE_URL", default="http://localhost:8000")

# Fall back to SMTP only when the Mailgun API backend above is NOT
# configured. This block runs later in the module than the
# `if MAILGUN_API_KEY:` guard, so setting EMAIL_BACKEND unconditionally
# here would clobber the anymail backend and make MAILGUN_API_KEY dead —
# the env-gating the PRD (Part 6) promises. (dev.py/test.py override
# EMAIL_BACKEND after this regardless, so the bug only bit prod.)
if not MAILGUN_API_KEY:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("MAILGUN_SMTP_HOST", default="localhost")
    EMAIL_PORT = env.int("MAILGUN_SMTP_PORT", default=25)
    EMAIL_HOST_USER = env("MAILGUN_SMTP_USER", default="")
    EMAIL_HOST_PASSWORD = env("MAILGUN_SMTP_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@null.community")
