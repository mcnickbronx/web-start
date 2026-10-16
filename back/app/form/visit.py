"""Откуда пришёл посетитель: метки из адреса страницы входа и канал — как его считают системы аналитики.

Визит запоминает сайт при первом заходе и присылает с заявкой (VisitIn в schemas.py).
"""
from urllib.parse import parse_qsl, urlsplit

from django.conf import settings

from form import models

Channel = models.FormRequest.Channel
PAID_MEDIUM_SET = {"cpc", "cpm", "cpa", "ppc", "cpv", "paid", "display", "banner", "retargeting"}
SOCIAL_MEDIUM_SET = {"social", "smm"}
EMAIL_MEDIUM_SET = {"email", "e-mail", "newsletter", "mailing"}
SEARCH_HOST_LIST = ["yandex.", "ya.ru", "google.", "bing.com", "go.mail.ru", "duckduckgo.com", "rambler.ru"]
SOCIAL_HOST_LIST = ["vk.com", "vk.ru", "ok.ru", "t.me", "telegram.", "dzen.ru", "youtube.com", "rutube.ru", "instagram.com", "facebook.com"]
#: Кроме utm_* — метки кликов рекламы: Яндекс Директ и Google Ads дописывают их к адресу сами
CLICK_ID_SET = {"yclid", "gclid"}


def _host_in(host: str, host_list: list[str]) -> bool:
    return any(host == item or host.endswith("." + item) or (item.endswith(".") and item in host) for item in host_list)


def parse_utm(landing_page: str) -> dict:
    """Метки из адреса страницы входа: все utm_* и клики рекламы, как есть."""
    utm = {}
    for key, value in parse_qsl(urlsplit(landing_page).query):
        key = key.lower()
        if (key.startswith("utm_") or key in CLICK_ID_SET) and value and key not in utm and len(utm) < 20:
            utm[key[:50]] = value[:200]
    return utm


def detect_channel(utm: dict, referrer: str) -> Channel:
    """Канал, как его считают системы аналитики: сначала метки, потом сайт, с которого пришли."""
    medium = utm.get("utm_medium", "").strip().lower()
    host = (urlsplit(referrer).hostname or "").removeprefix("www.")
    if host and host == (urlsplit(settings.SITE_URL).hostname or "").removeprefix("www."):
        host = ""  # переход внутри своего сайта — не источник
    if medium in PAID_MEDIUM_SET or CLICK_ID_SET & set(utm):
        return Channel.ADS
    if medium in SOCIAL_MEDIUM_SET or _host_in(host, SOCIAL_HOST_LIST):
        return Channel.SOCIAL
    if medium in EMAIL_MEDIUM_SET:
        return Channel.EMAIL
    if _host_in(host, SEARCH_HOST_LIST):
        return Channel.SEARCH
    if utm:
        return Channel.OTHER
    return Channel.REFERRAL if host else Channel.DIRECT
