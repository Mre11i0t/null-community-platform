from django import forms

from apps.chapters.models import Chapter
from apps.events.models import Event, EventSession, Venue
from apps.notifications.models import EventMailerTask


class LeadEventForm(forms.ModelForm):
    """Ported from leads/events/_form.html.erb.

    Rev 3: custom registration questions are edited as plain lines
    ("T-shirt size *" — trailing * marks required) instead of raw JSON."""

    custom_questions_text = forms.CharField(
        label="Custom registration questions",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        help_text="One question per line. End a line with * to make it required.",
    )

    class Meta:
        model = Event
        fields = [
            "event_type",
            "chapter",
            "name",
            "venue",
            "description",
            "can_show_on_homepage",
            "can_show_on_archive",
            "accepting_registration",
            "start_time",
            "end_time",
            "registration_start_time",
            "registration_end_time",
            "registration_instructions",
            "max_registration",
            "ready_for_announcement",
            "ready_for_notifications",
            "ready_for_reminders",
            "check_in_enabled",
            "auto_absent_enabled",
            "cancellation_deadline_hours",
            "image",
        ]
        widgets = {
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "end_time": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "registration_start_time": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "registration_end_time": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "registration_instructions": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "max_registration": forms.NumberInput(attrs={"class": "form-control"}),
            "event_type": forms.Select(attrs={"class": "form-control"}),
            "chapter": forms.Select(attrs={"class": "form-control"}),
            "venue": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["chapter"].queryset = user.managed_chapters()
            self.fields["venue"].queryset = user.managed_venues()
        if self.instance.pk and self.instance.custom_questions:
            self.initial["custom_questions_text"] = "\n".join(
                q["label"] + (" *" if q.get("required") else "")
                for q in self.instance.custom_questions
            )

    def clean_cancellation_deadline_hours(self):
        return self.cleaned_data.get("cancellation_deadline_hours") or 0

    def clean_custom_questions_text(self):
        questions = []
        for line in self.cleaned_data.get("custom_questions_text", "").splitlines():
            line = line.strip()
            if not line:
                continue
            required = line.endswith("*")
            questions.append({"label": line.rstrip("* ").strip(), "required": required})
        return questions

    def save(self, commit=True):
        event = super().save(commit=False)
        event.custom_questions = self.cleaned_data.get("custom_questions_text") or []
        if commit:
            event.save()
        return event


class LeadEventSessionForm(forms.ModelForm):
    """Ported from leads/event_sessions/_form.html.erb. The original's
    AJAX user-autocomplete is replaced by suggest_user (a JSON endpoint,
    same as original) feeding a plain user_id input — see template.

    Rev 3: co-speakers entered as comma-separated member emails; unknown
    addresses are a validation error, not a silent drop."""

    co_speaker_emails = forms.CharField(
        label="Co-speakers (comma-separated member emails)",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = EventSession
        fields = [
            "user",
            "name",
            "description",
            "start_time",
            "end_time",
            "need_projector",
            "need_microphone",
            "need_whiteboard",
            "presentation_url",
            "video_url",
            "placeholder",
            "image",
        ]
        widgets = {
            "user": forms.HiddenInput(),
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "end_time": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["co_speaker_emails"] = ", ".join(
                self.instance.co_speakers.values_list("email", flat=True)
            )

    def clean_co_speaker_emails(self):
        from apps.accounts.models import User

        emails = [e.strip().lower() for e in self.cleaned_data.get("co_speaker_emails", "").split(",") if e.strip()]
        users = list(User.objects.filter(email__in=emails))
        missing = set(emails) - {u.email.lower() for u in users}
        if missing:
            raise forms.ValidationError(f"No member account for: {', '.join(sorted(missing))}")
        return users

    def save(self, commit=True):
        session = super().save(commit=commit)
        if commit:
            session.co_speakers.set(self.cleaned_data.get("co_speaker_emails") or [])
        return session


class LeadVenueForm(forms.ModelForm):
    """Ported from leads/venues/_form.html.erb."""

    class Meta:
        model = Venue
        fields = [
            "chapter",
            "name",
            "description",
            "address",
            "map_url",
            "map_embedd_code",
            "contact_name",
            "contact_email",
            "contact_mobile",
            "contact_notes",
        ]
        widgets = {
            "chapter": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "map_embedd_code": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "contact_notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["chapter"].queryset = user.managed_chapters()


class LeadEventMailerTaskForm(forms.ModelForm):
    """Ported from leads/event_mailer_tasks/_form.html.erb."""

    class Meta:
        model = EventMailerTask
        fields = ["subject", "body", "registration_state", "ready_for_delivery"]
        widgets = {
            "subject": forms.TextInput(attrs={"class": "form-control"}),
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        }


class LeadChapterForm(forms.ModelForm):
    """Ported from leads/chapters/_form.html.erb — name/code/active are
    excluded, matching the controller stripping those from mass params."""

    class Meta:
        model = Chapter
        fields = [
            "chapter_email",
            "description",
            "city",
            "state",
            "country",
            "image",
            "twitter_handle",
            "facebook_profile",
            "github_profile",
            "linkedin_profile",
            "slideshare_profile",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }
