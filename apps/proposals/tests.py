import pytest
from django.core import mail
from django.urls import reverse

from apps.proposals.models import SessionProposal, SessionRequest
from tests.factories import (
    ChapterFactory,
    ChapterLeadFactory,
    EventSessionFactory,
    EventTypeFactory,
    SessionProposalFactory,
    SessionRequestFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


# --- SessionProposal ---------------------------------------------------------


def test_proposal_new_requires_login(client):
    response = client.get(reverse("proposals:proposal_new"))
    assert response.status_code == 302


def test_proposal_create_notifies_chapter_leads_by_email(client):
    chapter = ChapterFactory()
    lead = ChapterLeadFactory(chapter=chapter).user
    event_type = EventTypeFactory()
    user = UserFactory()
    client.force_login(user)

    response = client.post(
        reverse("proposals:proposal_new"),
        {
            "chapter": chapter.pk,
            "event_type": event_type.pk,
            "session_topic": "Exploiting Web Cache Poisoning",
            "session_description": "A deep dive into cache poisoning attacks.",
        },
    )

    assert response.status_code == 302
    proposal = SessionProposal.objects.get(session_topic="Exploiting Web Cache Poisoning")
    assert proposal.user == user

    assert len(mail.outbox) == 1
    assert lead.email in mail.outbox[0].to
    assert "Cache Poisoning" in mail.outbox[0].body or "New Session Proposal" in mail.outbox[0].subject


def test_proposal_create_does_not_email_when_chapter_has_no_leads(client):
    chapter = ChapterFactory()
    event_type = EventTypeFactory()
    client.force_login(UserFactory())

    client.post(
        reverse("proposals:proposal_new"),
        {
            "chapter": chapter.pk,
            "event_type": event_type.pk,
            "session_topic": "Topic",
            "session_description": "Description",
        },
    )

    assert len(mail.outbox) == 0


def test_proposal_edit_only_by_owner(client):
    proposal = SessionProposalFactory(session_topic="Original Topic")
    other_user = UserFactory()

    client.force_login(other_user)
    response = client.get(reverse("proposals:proposal_edit", args=[proposal.pk]))
    assert response.status_code == 404

    client.force_login(proposal.user)
    response = client.post(
        reverse("proposals:proposal_edit", args=[proposal.pk]),
        {
            "chapter": proposal.chapter.pk,
            "event_type": proposal.event_type.pk,
            "session_topic": "Updated Topic",
            "session_description": proposal.session_description,
        },
    )
    assert response.status_code == 302
    proposal.refresh_from_db()
    assert proposal.session_topic == "Updated Topic"


def test_proposal_index_filters_by_user_id(client):
    mine = SessionProposalFactory()
    other = SessionProposalFactory()
    client.force_login(mine.user)

    response = client.get(reverse("proposals:proposal_index"), {"user_id": mine.user.pk})

    proposals = list(response.context["page_obj"].object_list)
    assert mine in proposals
    assert other not in proposals


def test_proposal_show(client):
    proposal = SessionProposalFactory()
    client.force_login(UserFactory())
    response = client.get(reverse("proposals:proposal_show", args=[proposal.pk]))
    assert response.status_code == 200
    assert response.context["proposal"] == proposal


# --- SessionRequest -----------------------------------------------------------


def test_request_create_notifies_chapter_leads(client):
    chapter = ChapterFactory()
    lead = ChapterLeadFactory(chapter=chapter).user
    client.force_login(UserFactory())

    response = client.post(
        reverse("proposals:request_new"),
        {
            "chapter": chapter.pk,
            "session_topic": "Please cover container escape techniques",
            "session_description": "Would love a talk on this.",
        },
    )

    assert response.status_code == 302
    assert SessionRequest.objects.filter(session_topic__startswith="Please cover").exists()
    assert len(mail.outbox) == 1
    assert lead.email in mail.outbox[0].to


def test_request_show(client):
    session_request = SessionRequestFactory()
    client.force_login(UserFactory())
    response = client.get(reverse("proposals:request_show", args=[session_request.pk]))
    assert response.status_code == 200
    assert response.context["session_request"] == session_request


# --- Rev 3 CFP pipeline (closes gap #6) --------------------------------------


def test_status_transition_emails_proposer():
    from django.core import mail

    from apps.proposals.models import SessionProposal

    proposal = SessionProposalFactory()
    assert proposal.status == SessionProposal.STATUS_SUBMITTED

    mail.outbox.clear()
    proposal.set_status(SessionProposal.STATUS_ACCEPTED, note="Great topic!")

    proposal.refresh_from_db()
    assert proposal.status == SessionProposal.STATUS_ACCEPTED
    assert len(mail.outbox) == 1
    assert proposal.user.email in mail.outbox[0].to
    assert "Accepted" in mail.outbox[0].subject
    assert "Great topic!" in mail.outbox[0].body

    # no-op transition sends nothing
    mail.outbox.clear()
    proposal.set_status(SessionProposal.STATUS_ACCEPTED)
    assert len(mail.outbox) == 0


def test_lead_review_flow_scores_and_moves_to_under_review(client):
    from django.urls import reverse

    from apps.proposals.models import SessionProposal
    from tests.factories import ChapterLeadFactory

    proposal = SessionProposalFactory()
    lead = ChapterLeadFactory(chapter=proposal.chapter)
    client.force_login(lead.user)

    response = client.post(
        reverse("leads:proposal_review", args=[proposal.pk]),
        {"action": "review", "score": "4", "comment": "Solid abstract"},
    )
    assert response.status_code == 302
    proposal.refresh_from_db()
    assert proposal.status == SessionProposal.STATUS_UNDER_REVIEW
    assert proposal.average_score() == 4

    # updating own review doesn't duplicate
    client.post(
        reverse("leads:proposal_review", args=[proposal.pk]),
        {"action": "review", "score": "5", "comment": "Even better"},
    )
    assert proposal.reviews.count() == 1
    assert proposal.average_score() == 5


def test_review_denied_for_other_chapters_lead(client):
    from django.urls import reverse

    from tests.factories import ChapterLeadFactory

    proposal = SessionProposalFactory()
    outsider = ChapterLeadFactory()
    client.force_login(outsider.user)
    assert client.get(reverse("leads:proposal_review", args=[proposal.pk])).status_code == 403


def test_speaker_confirmation_flow(client):
    from django.urls import reverse

    session = EventSessionFactory()
    assert session.speaker_confirmed_at is None

    # only the assigned speaker can confirm
    stranger = UserFactory()
    client.force_login(stranger)
    assert client.post(reverse("events:session_confirm", args=[session.pk])).status_code == 404

    client.force_login(session.user)
    client.post(reverse("events:session_confirm", args=[session.pk]))
    session.refresh_from_db()
    assert session.speaker_confirmed_at is not None


def test_co_speakers_credited_on_profile(client):
    from django.urls import reverse

    session = EventSessionFactory()
    co = UserFactory()
    session.co_speakers.add(co)

    response = client.get(reverse("accounts:public_profile", args=[co.pk]))
    assert session in response.context["co_speaker_sessions"]
    assert "Co-speaker" in response.content.decode()
