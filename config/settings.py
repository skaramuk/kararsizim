"""Kararsızım — Django ayarları."""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_list(name):
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


# --- Temel güvenlik -------------------------------------------------------

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("1", "true", "yes")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY ortam değişkeni tanımlı olmalı.")
    SECRET_KEY = "yerel-gelistirme-icin-guvensiz-anahtar"

EXTRA_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".vercel.app", *EXTRA_HOSTS]
CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app", *[f"https://{host}" for host in EXTRA_HOSTS]]

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = False  # Vercel zaten HTTPS'e yönlendirir
    # Tarayıcıya "bu siteye 30 gün boyunca sadece HTTPS ile bağlan" der. Alt alan adlarını
    # (includeSubdomains) ve preload'u bilerek açmıyoruz; özel alan adı eklenince gözden geçir.
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    # `check --deploy` şu üç uyarıyı bilerek veriyor; gerekçeleriyle sessize alındı:
    #  W005/W021: includeSubdomains ve preload, *.vercel.app gibi ortak bir alan adında yanlış olur.
    #  W008: HTTP → HTTPS yönlendirmesini Vercel yapar; Django tarafında ayrıca açmaya gerek yok.
    SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W008", "security.W021"]


# --- Loglama --------------------------------------------------------------
# Vercel yalnızca stdout/stderr'i log olarak gösterir. Django varsayılanı DEBUG=False iken
# hataları konsola yazmaz (e-posta bekler); bu yüzden 500 hataları görünsün diye konsola yönlendiriyoruz.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "WARNING"),
        },
    },
}


# --- Uygulamalar ----------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "polls",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Veritabanı -----------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    if not DATABASE_URL.startswith(("postgres://", "postgresql://")):
        raise RuntimeError(
            "DATABASE_URL 'postgresql://' ile başlayan tam bir bağlantı adresi olmalı "
            "(Supabase → Connect → Transaction pooler). Değeri Vercel → Settings → "
            "Environment Variables bölümünden kontrol et."
        )
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=0, ssl_require=True)
    }
    # Supabase transaction pooler (port 6543) için gerekli:
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
    DATABASES["default"].setdefault("OPTIONS", {})["prepare_threshold"] = None
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Kimlik doğrulama -----------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "poll_list"
LOGOUT_REDIRECT_URL = "poll_list"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Yerelleştirme --------------------------------------------------------

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True


# --- Statik dosyalar ------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Manifest depolama collectstatic gerektirir; yerel geliştirmede (DEBUG=True) ve
# testlerde sade depolama kullanılır, üretimde sıkıştırılmış + hash'li dosyalar.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}
