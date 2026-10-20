"""Üyesiz oy verenleri tanımak için çerez ve IP özeti yardımcıları."""

import hashlib
import uuid

from django.conf import settings

COOKIE_NAME = "voter_id"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 yıl


def get_voter_token(request):
    """İmzalı `voter_id` çerezindeki UUID'yi döner; yok, bozuk ya da imzası geçersizse None."""
    raw = request.get_signed_cookie(COOKIE_NAME, default=None, max_age=COOKIE_MAX_AGE)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def set_voter_cookie(request, response, token):
    response.set_signed_cookie(
        COOKIE_NAME,
        str(token),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure(),
    )


def get_client_ip(request):
    # Vercel'de gerçek istemci IP'si X-Forwarded-For başlığının ilk değeridir.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def hash_ip(request):
    """Ham IP saklanmaz; sadece sha256(ip + SECRET_KEY) özeti tutulur."""
    ip = get_client_ip(request)
    if not ip:
        return ""
    return hashlib.sha256(f"{ip}{settings.SECRET_KEY}".encode("utf-8")).hexdigest()
