from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Q


class Poll(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls", verbose_name="yazar"
    )
    question = models.CharField(
        "soru",
        max_length=200,
        validators=[MinLengthValidator(5, "Soru en az 5 karakter olmalı.")],
    )
    description = models.TextField("açıklama", max_length=500, blank=True)
    created_at = models.DateTimeField("oluşturulma tarihi", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "anket"
        verbose_name_plural = "anketler"

    def __str__(self):
        return self.question


class Choice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="choices", verbose_name="anket")
    text = models.CharField("seçenek", max_length=100)
    order = models.PositiveSmallIntegerField("sıra", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "seçenek"
        verbose_name_plural = "seçenekler"

    def __str__(self):
        return self.text


class Vote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes", verbose_name="anket")
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE, related_name="votes", verbose_name="seçenek")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="votes",
        verbose_name="kullanıcı",
    )
    voter_token = models.UUIDField("oy veren kimliği", null=True, blank=True)
    ip_hash = models.CharField("IP özeti", max_length=64, blank=True)
    created_at = models.DateTimeField("oy tarihi", auto_now_add=True)

    class Meta:
        verbose_name = "oy"
        verbose_name_plural = "oylar"
        constraints = [
            models.UniqueConstraint(
                fields=["poll", "user"],
                condition=Q(user__isnull=False),
                name="unique_vote_per_user",
            ),
            models.UniqueConstraint(
                fields=["poll", "voter_token"],
                condition=Q(voter_token__isnull=False),
                name="unique_vote_per_token",
            ),
            models.CheckConstraint(
                condition=Q(user__isnull=False) | Q(voter_token__isnull=False),
                name="vote_has_voter_identity",
            ),
        ]

    def __str__(self):
        return f"{self.poll_id} → {self.choice_id}"
