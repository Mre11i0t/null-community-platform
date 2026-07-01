from django import forms
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox

from .models import EventRegistration, EventSessionComment


class EventRegistrationForm(forms.ModelForm):
    """Ported from app/views/event_registrations/_form.html.erb."""

    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)

    class Meta:
        model = EventRegistration
        fields = ["visible"]


class EventSessionCommentForm(forms.ModelForm):
    """Ported from app/views/event_session_comments (create action's reCAPTCHA)."""

    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)

    class Meta:
        model = EventSessionComment
        fields = ["comment_body"]
        widgets = {"comment_body": forms.Textarea(attrs={"class": "form-control", "rows": 4})}
