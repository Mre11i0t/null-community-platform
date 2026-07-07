"""Shared factory_boy factories, used by every app's tests.py."""

import datetime

import factory
from django.utils import timezone

from apps.accounts.models import User
from apps.chapters.models import Chapter, ChapterLead
from apps.content.models import Page
from apps.events.models import (
    Event,
    EventRegistration,
    EventSession,
    EventSessionComment,
    EventType,
    Venue,
)
from apps.notifications.models import EventAutomaticNotificationTask, EventMailerTask
from apps.proposals.models import SessionProposal, SessionRequest


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    name = factory.Faker("name")
    is_active = True

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        obj.set_password(extracted or "testpass123")
        if create:
            obj.save()


    @factory.post_generation
    def coc(self, create, extracted, **kwargs):
        """Rev 3: most tests exercise flows that assume the member has
        accepted the current CoC (it's required at signup); pass
        coc=False to get a user who hasn't."""
        if create and extracted is not False:
            self.acknowledge_coc()

class ChapterFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Chapter

    name = factory.Sequence(lambda n: f"Test Chapter {n}")
    description = "A test chapter."
    active = True
    chapter_email = factory.LazyAttribute(lambda o: f"{o.name.lower().replace(' ', '')}@example.com")


class ChapterLeadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ChapterLead

    user = factory.SubFactory(UserFactory)
    chapter = factory.SubFactory(ChapterFactory)
    active = True


class VenueFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Venue

    chapter = factory.SubFactory(ChapterFactory)
    name = factory.Sequence(lambda n: f"Test Venue {n}")
    address = "123 Test Street"
    contact_name = "Venue Contact"


class EventTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EventType
        django_get_or_create = ("name",)

    name = "Monthly Meet"
    description = "A regular meetup."


class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Event

    name = factory.Sequence(lambda n: f"Test Event {n}")
    chapter = factory.SubFactory(ChapterFactory)
    venue = factory.SubFactory(VenueFactory, chapter=factory.SelfAttribute("..chapter"))
    event_type = factory.SubFactory(EventTypeFactory)
    description = "An event description."
    public = True
    accepting_registration = True
    start_time = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=10))
    end_time = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=10, hours=2))
    registration_start_time = factory.LazyFunction(lambda: timezone.now() - datetime.timedelta(days=1))
    registration_end_time = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(days=9))


class EventSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EventSession

    event = factory.SubFactory(EventFactory)
    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Test Session {n}")
    description = "A session description."
    start_time = factory.LazyAttribute(lambda o: o.event.start_time)
    end_time = factory.LazyAttribute(lambda o: o.event.start_time + datetime.timedelta(minutes=30))
    placeholder = False


class EventRegistrationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EventRegistration

    event = factory.SubFactory(EventFactory)
    user = factory.SubFactory(UserFactory)


class EventSessionCommentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EventSessionComment

    event_session = factory.SubFactory(EventSessionFactory)
    user = factory.SubFactory(UserFactory)
    comment_body = "A test comment."


class SessionProposalFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SessionProposal

    chapter = factory.SubFactory(ChapterFactory)
    user = factory.SubFactory(UserFactory)
    event_type = factory.SubFactory(EventTypeFactory)
    session_topic = "A proposed topic"
    session_description = "Description of the proposed session."


class SessionRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SessionRequest

    chapter = factory.SubFactory(ChapterFactory)
    user = factory.SubFactory(UserFactory)
    session_topic = "A requested topic"
    session_description = "Description of the requested session."


class EventMailerTaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EventMailerTask

    event = factory.SubFactory(EventFactory)
    subject = "Test Blast"
    body = "Test body."


class EventAutomaticNotificationTaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EventAutomaticNotificationTask

    event = factory.SubFactory(EventFactory)
    mode = EventAutomaticNotificationTask.MODE_ANNOUNCEMENT


class PageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Page

    name = factory.Sequence(lambda n: f"test-page-{n}")
    description = "A short description."
    navigation_name = "Test Page"
    title = "Test Page Title"
    content = "Page content."
    published = True
