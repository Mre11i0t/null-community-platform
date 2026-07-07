from django import forms
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox

from .models import EventRegistration, EventSessionComment


class EventRegistrationForm(forms.ModelForm):
    """Ported from app/views/event_registrations/_form.html.erb.

    Rev 3: the event's leader-defined custom questions (Event.custom_questions,
    a list of {"label", "required"}) become real form fields, and answers
    land in EventRegistration.custom_answers."""

    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)

    class Meta:
        model = EventRegistration
        fields = ["visible"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._question_labels = []
        event = getattr(self.instance, "event", None)
        for i, question in enumerate(event.custom_questions if event else []):
            label = question.get("label", "").strip()
            if not label:
                continue
            field_name = f"custom_q_{i}"
            self.fields[field_name] = forms.CharField(
                label=label,
                required=bool(question.get("required")),
                widget=forms.TextInput(attrs={"class": "form-control"}),
            )
            self._question_labels.append((field_name, label))

    def save(self, commit=True):
        registration = super().save(commit=False)
        registration.custom_answers = {
            label: self.cleaned_data.get(field_name, "")
            for field_name, label in self._question_labels
        }
        if commit:
            registration.save()
        return registration


class EventSessionCommentForm(forms.ModelForm):
    """Ported from app/views/event_session_comments (create action's reCAPTCHA)."""

    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)

    class Meta:
        model = EventSessionComment
        fields = ["comment_body"]
        widgets = {"comment_body": forms.Textarea(attrs={"class": "form-control", "rows": 4})}
