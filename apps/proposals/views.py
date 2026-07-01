from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SessionProposalForm, SessionRequestForm
from .models import SessionProposal, SessionRequest


@login_required
def proposal_index(request):
    """Mirrors SessionProposalsController#index."""
    proposals = SessionProposal.objects.select_related("chapter", "event_type").order_by("-created_at")
    user_id = request.GET.get("user_id")
    if user_id:
        proposals = proposals.filter(user_id=user_id)
    page_obj = Paginator(proposals, 10).get_page(request.GET.get("page"))
    return render(request, "proposals/proposal_index.html", {"page_obj": page_obj})


@login_required
def proposal_new(request):
    """Mirrors SessionProposalsController#new/#create."""
    if request.method == "POST":
        form = SessionProposalForm(request.POST)
        if form.is_valid():
            proposal = form.save(commit=False)
            proposal.user = request.user
            proposal.save()
            return redirect("proposals:proposal_show", pk=proposal.pk)
    else:
        form = SessionProposalForm()
    return render(request, "proposals/proposal_form.html", {"form": form, "is_edit": False})


@login_required
def proposal_edit(request, pk):
    """Mirrors SessionProposalsController#edit/#update — owner only."""
    proposal = get_object_or_404(SessionProposal, pk=pk, user=request.user)
    if request.method == "POST":
        form = SessionProposalForm(request.POST, instance=proposal)
        if form.is_valid():
            form.save()
            return redirect("proposals:proposal_show", pk=proposal.pk)
    else:
        form = SessionProposalForm(instance=proposal)
    return render(request, "proposals/proposal_form.html", {"form": form, "is_edit": True, "proposal": proposal})


@login_required
def proposal_show(request, pk):
    """Mirrors SessionProposalsController#show."""
    proposal = get_object_or_404(SessionProposal, pk=pk)
    return render(request, "proposals/proposal_show.html", {"proposal": proposal})


@login_required
def request_new(request):
    """Mirrors SessionRequestsController#new/#create."""
    if request.method == "POST":
        form = SessionRequestForm(request.POST)
        if form.is_valid():
            session_request = form.save(commit=False)
            session_request.user = request.user
            session_request.save()
            return redirect("proposals:request_show", pk=session_request.pk)
    else:
        form = SessionRequestForm()
    return render(request, "proposals/request_form.html", {"form": form})


@login_required
def request_show(request, pk):
    """Mirrors SessionRequestsController#show."""
    session_request = get_object_or_404(SessionRequest, pk=pk)
    return render(request, "proposals/request_show.html", {"session_request": session_request})
