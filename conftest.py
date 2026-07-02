import pytest
from django import forms as django_forms
from django.template.context import BaseContext
from django_recaptcha.fields import ReCaptchaField


def _base_context_copy(self):
    """Django 5.1's BaseContext.__copy__ does `duplicate = copy(super())`,
    which relies on `copy.copy()` transparently following a `super` proxy
    through to the underlying instance — that stopped working on Python
    3.14 (`'super' object has no attribute 'dicts'`), breaking every
    templated response captured by django.test.Client (it copies the
    render context for `response.context` on every request, not just
    when a test reads it). Not an app bug; patch the copy directly."""
    duplicate = self.__class__.__new__(self.__class__)
    duplicate.__dict__.update(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate


BaseContext.__copy__ = _base_context_copy


@pytest.fixture(autouse=True)
def bypass_recaptcha(monkeypatch):
    """Every form with a captcha field (signup, RSVP, session comments)
    otherwise calls out to Google's siteverify endpoint on validate().
    Skip the network call in tests but keep the "required" check, so a
    POST that forgets to send a captcha value still fails validation."""

    def fake_validate(self, value):
        django_forms.CharField.validate(self, value)

    monkeypatch.setattr(ReCaptchaField, "validate", fake_validate)
