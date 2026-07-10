from django import forms

from apps.core.captcha import build_captcha_field

from .models import EventRegistration, EventSessionComment


class EventRegistrationForm(forms.ModelForm):
    """Ported from app/views/event_registrations/_form.html.erb.

    Rev 3: the event's leader-defined custom questions (Event.custom_questions,
    a list of {"label", "required"}) become real form fields, and answers
    land in EventRegistration.custom_answers."""

    captcha = build_captcha_field(action="rsvp")

    class Meta:
        model = EventRegistration
        fields = ["visible"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rev 3 trust & safety: if the member hasn't accepted the current
        # CoC version (e.g. it was bumped after they signed up), the RSVP
        # is the re-prompt point.
        from django.conf import settings

        user = getattr(self.instance, "user", None)
        self._needs_coc = bool(user and user.pk and not user.has_acknowledged_coc())
        if self._needs_coc:
            self.fields["coc_accept"] = forms.BooleanField(
                label=f"I have read and agree to the Code of Conduct (v{settings.COC_VERSION})",
                required=True,
                error_messages={"required": "You must accept the Code of Conduct to register."},
            )

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
            if self._needs_coc and self.cleaned_data.get("coc_accept"):
                registration.user.acknowledge_coc()
        return registration


class EventSessionCommentForm(forms.ModelForm):
    """Ported from app/views/event_session_comments (create action's reCAPTCHA)."""

    captcha = build_captcha_field(action="session_comment")

    class Meta:
        model = EventSessionComment
        fields = ["comment_body"]
        widgets = {"comment_body": forms.Textarea(attrs={"class": "form-control", "rows": 4})}
