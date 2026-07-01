from allauth.account.forms import SignupForm
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox


class CaptchaSignupForm(SignupForm):
    """Adds reCAPTCHA to allauth's signup form, mirroring the original
    RegistrationsController's before_filter :devise_verify_captcha."""

    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)
