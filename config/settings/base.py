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
]

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
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

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
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

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

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("MAILGUN_SMTP_HOST", default="localhost")
EMAIL_PORT = env.int("MAILGUN_SMTP_PORT", default=25)
EMAIL_HOST_USER = env("MAILGUN_SMTP_USER", default="")
EMAIL_HOST_PASSWORD = env("MAILGUN_SMTP_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@null.community")
