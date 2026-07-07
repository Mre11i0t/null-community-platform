from django import forms

from apps.chapters.models import Chapter
from apps.events.models import Event, EventSession, Venue
from apps.notifications.models import EventMailerTask


class LeadEventForm(forms.ModelForm):
    """Ported from leads/events/_form.html.erb."""

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


class LeadEventSessionForm(forms.ModelForm):
    """Ported from leads/event_sessions/_form.html.erb. The original's
    AJAX user-autocomplete is replaced by suggest_user (a JSON endpoint,
    same as original) feeding a plain user_id input — see template."""

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
