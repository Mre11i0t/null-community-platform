"""Ported from SessionProposal/SessionRequest#notify_users (after_create).
Emails every active lead of the target chapter when a member submits
a proposal/request — see app/mailers/misc_mailer.rb + its two text
templates for the original content this mirrors.
"""

from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string

from .models import SessionProposal, SessionRequest


@receiver(post_save, sender=SessionProposal)
def notify_leads_of_proposal(sender, instance, created, **kwargs):
    if not created:
        return
    recipients = [lead.email for lead in instance.chapter.leads()]
    if not recipients:
        return
    body = render_to_string("proposals/emails/session_proposal_mail.txt", {"session_proposal": instance})
    send_mail(
        subject=f"[Notification] New Session Proposal #{instance.pk}",
        message=body,
        from_email=None,
        recipient_list=recipients,
    )


@receiver(post_save, sender=SessionRequest)
def notify_leads_of_request(sender, instance, created, **kwargs):
    if not created:
        return
    recipients = [lead.email for lead in instance.chapter.leads()]
    if not recipients:
        return
    body = render_to_string("proposals/emails/session_request_mail.txt", {"session_request": instance})
    send_mail(
        subject=f"[Notification] New Session Request #{instance.pk}",
        message=body,
        from_email=None,
        recipient_list=recipients,
    )
