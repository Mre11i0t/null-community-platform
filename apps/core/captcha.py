"""Deployment-selectable reCAPTCHA field.

The platform's forms were built around the v2 "I'm not a robot" checkbox
(mirroring the original Rails app), and Google's published test keys — the
dev/test default — only support that widget. The showcase's real keys are
score-based v3 keys, which a v2 checkbox rejects outright ("Invalid key
type"). RECAPTCHA_WIDGET=v3 switches every captcha-guarded form to the
invisible v3 flow; any other value keeps the v2 checkbox.
"""

from django.conf import settings
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox, ReCaptchaV3


def build_captcha_field(action):
    """Return a ReCaptchaField matching the deployment's key type.

    ``action`` labels the request in Google's v3 analytics and is verified
    against the token on submit; it is ignored by the v2 checkbox.
    """
    if getattr(settings, "RECAPTCHA_WIDGET", "v2_checkbox") == "v3":
        return ReCaptchaField(widget=ReCaptchaV3(action=action))
    return ReCaptchaField(widget=ReCaptchaV2Checkbox)
