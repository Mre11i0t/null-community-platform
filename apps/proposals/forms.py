from django import forms

from .models import SessionProposal, SessionRequest


class SessionProposalForm(forms.ModelForm):
    class Meta:
        model = SessionProposal
        fields = ["chapter", "event_type", "session_topic", "session_description"]
        widgets = {
            "chapter": forms.Select(attrs={"class": "form-control"}),
            "event_type": forms.Select(attrs={"class": "form-control"}),
            "session_topic": forms.TextInput(attrs={"class": "form-control"}),
            "session_description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.chapters.models import Chapter

        self.fields["chapter"].queryset = Chapter.active_chapters()


class SessionRequestForm(forms.ModelForm):
    class Meta:
        model = SessionRequest
        fields = ["chapter", "session_topic", "session_description"]
        widgets = {
            "chapter": forms.Select(attrs={"class": "form-control"}),
            "session_topic": forms.TextInput(attrs={"class": "form-control"}),
            "session_description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.chapters.models import Chapter

        self.fields["chapter"].queryset = Chapter.active_chapters()
