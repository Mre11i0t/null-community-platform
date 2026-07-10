from .dev import *  # noqa: F401,F403

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Pin privileged-2FA OFF for the suite regardless of any REQUIRE_2FA_FOR_PRIVILEGED
# that leaks in from the shell env (e.g. a sourced showcase .env). The one test
# that exercises enforcement sets it True locally via settings override.
REQUIRE_2FA_FOR_PRIVILEGED = False

# Likewise pin the captcha to the v2 test keys regardless of any real keys in
# the developer's .env (dev.py prefers those): the suite posts the checkbox
# widget's fixed 'g-recaptcha-response' payload, while a v3 widget would read
# its token from a differently-named field (validation itself is bypassed in
# conftest either way).
RECAPTCHA_PUBLIC_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
RECAPTCHA_PRIVATE_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"
RECAPTCHA_WIDGET = "v2_checkbox"
SILENCED_SYSTEM_CHECKS = ["django_recaptcha.recaptcha_test_key_error"]
