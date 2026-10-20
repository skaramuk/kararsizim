from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Choice, Poll

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
