import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services, voter
from .forms import PollCreateForm
from .models import Poll

User = get_user_model()

POLLS_PER_PAGE = 20


def _poll_queryset():
    """Liste kartları için: yazar tek JOIN ile, oy ve seçenek sayıları tek sorguda gelir."""
    return (
        Poll.objects.select_related("author")
        .annotate(vote_count=Count("votes", distinct=True), choice_count=Count("choices", distinct=True))
        .order_by("-created_at", "-pk")
    )


def _identity(request):
    """Ziyaretçinin kimliği: (giriş yapmışsa kullanıcı, çerezdeki voter_id). Biri ya da ikisi None olabilir."""
    user = request.user if request.user.is_authenticated else None
    return user, voter.get_voter_token(request)


def _poll_list_page(request, template, queryset, extra_context=None):
    page_obj = Paginator(queryset, POLLS_PER_PAGE).get_page(request.GET.get("page"))
    user, token = _identity(request)
    voted_poll_ids = services.get_voted_poll_ids([poll.pk for poll in page_obj], user, token)
    context = {"page_obj": page_obj, "voted_poll_ids": voted_poll_ids, **(extra_context or {})}
    return render(request, template, context)


def poll_list(request):
    # `?sirala=populer` → en çok oy alan üstte (eşitlikte en yeni); başka her değer "en yeni" sayılır.
    sort = "populer" if request.GET.get("sirala") == "populer" else "yeni"
    queryset = _poll_queryset()
    if sort == "populer":
        queryset = queryset.order_by("-vote_count", "-created_at", "-pk")
    return _poll_list_page(request, "polls/poll_list.html", queryset, {"sort": sort})


def user_polls(request, username):
    profile_user = get_object_or_404(User, username__iexact=username)
    return _poll_list_page(
        request,
        "polls/user_polls.html",
        _poll_queryset().filter(author=profile_user),
        {"profile_user": profile_user},
    )


def _render_detail(request, poll, status=200):
    user, token = _identity(request)
    vote = services.get_user_vote(poll, user, token)
    is_owner = request.user.is_authenticated and request.user.pk == poll.author_id
    # Oy vermemiş ziyaretçi sonuçları görmez (oyların başkalarını etkilemesini önlemek için); sahibi her zaman görür.
    results = services.get_results(poll) if (vote or is_owner) else None
    context = {
        "poll": poll,
        "is_owner": is_owner,
        "results": results,
        "voted_choice_id": vote.choice_id if vote else None,
        "has_voted": vote is not None,
    }
    return render(request, "polls/poll_detail.html", context, status=status)


def poll_detail(request, pk):
    poll = get_object_or_404(_poll_queryset().prefetch_related("choices"), pk=pk)
    return _render_detail(request, poll)


def _wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


@require_POST
def poll_vote(request, pk):
    poll = get_object_or_404(_poll_queryset().prefetch_related("choices"), pk=pk)
    user, token = _identity(request)
    new_token = token is None
    if new_token:
        token = uuid.uuid4()

    try:
        vote = services.cast_vote(
            poll, request.POST.get("choice"), user, token, voter.hash_ip(request)
        )
    except services.AlreadyVoted as error:
        if _wants_json(request):
            return JsonResponse({"ok": False, "error": error.message}, status=409)
        messages.info(request, error.message)
        return redirect("poll_detail", pk=poll.pk)
    except services.InvalidChoice as error:
        if _wants_json(request):
            return JsonResponse({"ok": False, "error": error.message}, status=400)
        messages.error(request, "Bir seçenek seçmelisin." if not request.POST.get("choice") else error.message)
        return _render_detail(request, poll, status=400)

    if _wants_json(request):
        data = services.get_results(poll)
        response = JsonResponse({"ok": True, "voted_choice_id": vote.choice_id, **data})
    else:
        messages.success(request, "Oyun kaydedildi.")
        response = redirect("poll_detail", pk=poll.pk)
    if new_token:
        voter.set_voter_cookie(request, response, token)
    return response


@login_required
def poll_create(request):
    form = PollCreateForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        poll = form.save(request.user)
        messages.success(request, "Anketin yayında!")
        return redirect("poll_detail", pk=poll.pk)
    return render(request, "polls/poll_create.html", {"form": form})


@login_required
def poll_delete(request, pk):
    # Sahibi olmayan 404 alır: başkasının anketinin varlığı sızdırılmaz.
    poll = get_object_or_404(Poll, pk=pk, author=request.user)
    if request.method == "POST":
        poll.delete()
        messages.success(request, "Anket silindi.")
        return redirect("poll_list")
    return render(request, "polls/poll_confirm_delete.html", {"poll": poll})
