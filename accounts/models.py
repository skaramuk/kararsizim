from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.db.models.functions import Lower

RESERVED_USERNAMES = {
    "admin",
    "kararsizim",
    "yonetici",
    "destek",
    "anket",
    "hesap",
    "kullanici",
    "api",
    "static",
}

username_validators = [
    MinLengthValidator(3, "Kullanıcı adı en az 3 karakter olmalı."),
    RegexValidator(
        r"^[A-Za-z0-9_.]+$",
        "Kullanıcı adı sadece harf, rakam, alt çizgi (_) ve nokta (.) içerebilir.",
    ),
]


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, username, password, **extra_fields):
        if not email:
            raise ValueError("E-posta zorunludur.")
        if not username:
            raise ValueError("Kullanıcı adı zorunludur.")
        user = self.model(email=self.normalize_email(email).lower(), username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, username, password, **extra_fields)

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True or extra_fields["is_superuser"] is not True:
            raise ValueError("Süper kullanıcı is_staff ve is_superuser olmalıdır.")
        return self._create_user(email, username, password, **extra_fields)


class User(AbstractUser):
    first_name = None
    last_name = None

    email = models.EmailField("e-posta", unique=True)
    username = models.CharField(
        "kullanıcı adı",
        max_length=20,
        unique=True,
        validators=username_validators,
        error_messages={"unique": "Bu kullanıcı adı zaten alınmış."},
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("username"), name="unique_username_ci"),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username
