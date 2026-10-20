from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

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


def _paginate(request, queryset):
    return Paginator(queryset, POLLS_PER_PAGE).get_page(request.GET.get("page"))


def poll_list(request):
    page_obj = _paginate(request, _poll_queryset())
    return render(request, "polls/poll_list.html", {"page_obj": page_obj})


def user_polls(request, username):
    profile_user = get_object_or_404(User, username__iexact=username)
    page_obj = _paginate(request, _poll_queryset().filter(author=profile_user))
    return render(request, "polls/user_polls.html", {"profile_user": profile_user, "page_obj": page_obj})


def poll_detail(request, pk):
    poll = get_object_or_404(_poll_queryset().prefetch_related("choices"), pk=pk)
    return render(
        request,
        "polls/poll_detail.html",
        {"poll": poll, "is_owner": request.user.is_authenticated and request.user.pk == poll.author_id},
    )


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
