from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q

from .models import Choice, Poll, Vote

MIN_CHOICES = 2
MAX_CHOICES = 5
CHOICE_MAX_LENGTH = 100


def clean_choices(raw_choices):
    """Seçenek metinlerini kırpar, boşları atar ve kuralları doğrular (2–5 adet, tekrar yok)."""
    cleaned = [text.strip() for text in raw_choices if text and text.strip()]

    if len(cleaned) < MIN_CHOICES:
        raise ValidationError(f"En az {MIN_CHOICES} seçenek girmelisin.")
    if len(cleaned) > MAX_CHOICES:
        raise ValidationError(f"En fazla {MAX_CHOICES} seçenek ekleyebilirsin.")
    if any(len(text) > CHOICE_MAX_LENGTH for text in cleaned):
        raise ValidationError(f"Her seçenek en fazla {CHOICE_MAX_LENGTH} karakter olabilir.")
    if len({text.casefold() for text in cleaned}) != len(cleaned):
        raise ValidationError("Aynı seçeneği birden fazla kez ekleyemezsin.")
    return cleaned


def create_poll(author, question, description, raw_choices):
    """Anketi ve seçeneklerini tek işlemde oluşturur. Geçersizse ValidationError fırlatır."""
    choices = clean_choices(raw_choices)
    poll = Poll(author=author, question=question.strip(), description=description.strip())
    poll.full_clean()

    with transaction.atomic():
        poll.save()
        Choice.objects.bulk_create(
            [Choice(poll=poll, text=text, order=index) for index, text in enumerate(choices)]
        )
    return poll


# --- Oylama ----------------------------------------------------------------


class VoteError(Exception):
    """Oy verme kurallarının ihlali; `message` kullanıcıya gösterilir."""

    message = "Oy kaydedilemedi."

    def __str__(self):
        return self.message


class InvalidChoice(VoteError):
    message = "Geçersiz seçenek."


class AlreadyVoted(VoteError):
    message = "Bu ankete zaten oy verdin."


def _identity_filter(user, voter_token):
    """Bir ziyaretçinin oylarını bulan filtre: üyeli ise `user`, çerezi varsa `voter_token`."""
    condition = Q()
    if user is not None:
        condition |= Q(user=user)
    if voter_token is not None:
        condition |= Q(voter_token=voter_token)
    return condition


def get_user_vote(poll, user, voter_token):
    """Ziyaretçinin bu ankette verdiği oy, yoksa None."""
    condition = _identity_filter(user, voter_token)
    if not condition:
        return None
    return Vote.objects.filter(poll=poll).filter(condition).first()


def get_voted_poll_ids(poll_ids, user, voter_token):
    """Verilen anketlerden ziyaretçinin oy verdiklerinin ID'leri (tek sorgu)."""
    condition = _identity_filter(user, voter_token)
    if not condition:
        return set()
    return set(Vote.objects.filter(poll_id__in=poll_ids).filter(condition).values_list("poll_id", flat=True))


def cast_vote(poll, choice_id, user, voter_token, ip_hash=""):
    """Oyu kaydeder. Seçenek ankete ait değilse InvalidChoice, aynı kimlik tekrar oy verirse AlreadyVoted."""
    if user is None and voter_token is None:
        raise ValueError("Oy için kullanıcı ya da voter_token gerekir.")
    try:
        choice_pk = int(choice_id)
    except (TypeError, ValueError):
        raise InvalidChoice() from None

    choice = Choice.objects.filter(pk=choice_pk, poll=poll).first()
    if choice is None:
        raise InvalidChoice()
    if get_user_vote(poll, user, voter_token) is not None:
        raise AlreadyVoted()

    try:
        with transaction.atomic():
            return Vote.objects.create(
                poll=poll, choice=choice, user=user, voter_token=voter_token, ip_hash=ip_hash
            )
    except IntegrityError:
        # Aynı anda gelen ikinci istek: veritabanı kısıtı devreye girdi.
        raise AlreadyVoted() from None


def _percent(count, total):
    if not total:
        return 0
    return (count * 200 + total) // (2 * total)  # en yakın tam sayıya (yarım yukarı) yuvarlar


def get_results(poll):
    """Seçeneklerin oy sayıları ve yüzdeleri; tek sorgu."""
    rows = list(
        poll.choices.annotate(count=Count("votes")).order_by("order", "id").values("id", "text", "count")
    )
    total = sum(row["count"] for row in rows)
    results = [{**row, "percent": _percent(row["count"], total)} for row in rows]
    return {"total": total, "results": results}
