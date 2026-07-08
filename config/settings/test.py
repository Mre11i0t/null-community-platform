from .dev import *  # noqa: F401,F403

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Pin privileged-2FA OFF for the suite regardless of any REQUIRE_2FA_FOR_PRIVILEGED
# that leaks in from the shell env (e.g. a sourced showcase .env). The one test
# that exercises enforcement sets it True locally via settings override.
REQUIRE_2FA_FOR_PRIVILEGED = False
