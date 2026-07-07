from allauth.account.forms import SignupForm
from django import forms
from django.conf import settings
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox


class CaptchaSignupForm(SignupForm):
    """Adds reCAPTCHA to allauth's signup form, mirroring the original
    RegistrationsController's before_filter :devise_verify_captcha.

    Rev 3: also requires acceptance of the Code of Conduct (versioned;
    the accepted version is recorded on the account)."""

    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)
    coc_accept = forms.BooleanField(
        label=f"I have read and agree to the Code of Conduct (v{settings.COC_VERSION})",
        required=True,
        error_messages={"required": "You must accept the Code of Conduct to join."},
    )

    def save(self, request):
        user = super().save(request)
        user.acknowledge_coc()
        return user
