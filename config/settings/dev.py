from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# DEBUG_TOOLBAR=0 disables the toolbar (clean UI screenshots / demos)
if env.bool("DEBUG_TOOLBAR", default=True):  # noqa: F405
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE
    INTERNAL_IPS = ["127.0.0.1"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=True)  # noqa: F405

# Mandatory in prod (mirrors Devise :confirmable), optional in dev so
# manually-created/seeded users can log in without clicking a console
# email link on every fresh migrate.
ACCOUNT_EMAIL_VERIFICATION = "optional"

# Real reCAPTCHA keys from the env (e.g. the repo-root .env) win, together
# with their RECAPTCHA_WIDGET — for score-based v3 keys to render in dev,
# add localhost to the key's allowed domains in the Google console.
# Without env keys, fall back to django-recaptcha's official published test
# keys — the widget always shows a pre-checked checkbox and Google's
# siteverify endpoint always returns success for these specific keys
# (server-side verification still makes a real HTTP call to Google, just
# always passes). The test keys are v2-only (Google publishes no v3 test
# keys), so the fallback pins the checkbox widget. See
# https://developers.google.com/recaptcha/docs/faq#id-like-to-run-automated-tests-with-recaptcha-what-should-i-do
if not env("RECAPTCHA_PUBLIC_KEY", default=""):  # noqa: F405
    RECAPTCHA_PUBLIC_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
    RECAPTCHA_PRIVATE_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
    RECAPTCHA_WIDGET = "v2_checkbox"
    SILENCED_SYSTEM_CHECKS = ["django_recaptcha.recaptcha_test_key_error"]
