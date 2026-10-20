"""Faz 5: sıralama sekmeleri, bağlantı kopyalama, meta etiketleri, hata sayfaları, erişilebilirlik."""

import re
import uuid
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import Client, TestCase

from .models import Vote
from .tests import make_poll, make_user

CSS_PATH = Path(settings.BASE_DIR) / "static" / "css" / "style.css"


def add_votes(poll, count):
    choice = poll.choices.first()
    for _ in range(count):
        Vote.objects.create(poll=poll, choice=choice, voter_token=uuid.uuid4())


class SortTabTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.old_popular = make_poll(self.user, "Eski ama çok oylanan anket")
        self.mid = make_poll(self.user, "Ortadaki az oylanan anket")
        self.newest = make_poll(self.user, "En yeni ama oysuz anket")
        add_votes(self.old_popular, 5)
        add_votes(self.mid, 2)

    def polls(self, url):
        return list(self.client.get(url).context["page_obj"])

    def test_default_is_newest_first(self):
        self.assertEqual(self.polls("/"), [self.newest, self.mid, self.old_popular])

    def test_popular_orders_by_votes_then_newest(self):
        self.assertEqual(self.polls("/?sirala=populer"), [self.old_popular, self.mid, self.newest])

    def test_ties_fall_back_to_newest(self):
        add_votes(self.newest, 2)  # mid ile eşit (2 oy); newest daha yeni
        self.assertEqual(self.polls("/?sirala=populer"), [self.old_popular, self.newest, self.mid])

    def test_unknown_sort_value_falls_back_to_newest(self):
        for value in ("", "yeni", "xyz", "populer'--", "POPULER"):
            with self.subTest(value=value):
                response = self.client.get("/", {"sirala": value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["sort"], "yeni")

    def test_tabs_mark_current_page(self):
        newest = self.client.get("/").content.decode()
        popular = self.client.get("/?sirala=populer").content.decode()
        self.assertRegex(newest, r'<a class="tab" href="/" aria-current="page">En yeni</a>')
        self.assertNotRegex(newest, r'sirala=populer"[^>]*aria-current')
        self.assertRegex(popular, r'sirala=populer" aria-current="page">En çok oylanan</a>')
        self.assertNotRegex(popular, r'href="/" aria-current')

    def test_titles_differ_by_sort(self):
        self.assertContains(self.client.get("/?sirala=populer"), "<title>En çok oylanan anketler — Kararsızım</title>")
        self.assertContains(self.client.get("/"), "<title>Kararsızım — Kararsız kaldığında topluluğa sor</title>")

    def test_pagination_keeps_sort(self):
        for index in range(22):
            make_poll(self.user, f"Sayfalama için anket {index:02d}")
        popular = self.client.get("/?sirala=populer").content.decode()
        self.assertIn('href="?page=2&amp;sirala=populer"', popular)
        page2 = self.client.get("/?sirala=populer&page=2").content.decode()
        self.assertIn('href="?page=1&amp;sirala=populer"', page2)
        newest = self.client.get("/").content.decode()
        self.assertIn('href="?page=2"', newest)
        self.assertNotIn("sirala=populer&amp;", newest)

    def test_user_page_has_no_tabs(self):
        self.assertNotContains(self.client.get("/kullanici/semih/"), 'class="tabs"')

    def test_empty_list_in_popular_view(self):
        Vote.objects.all().delete()
        self.old_popular.delete(), self.mid.delete(), self.newest.delete()
        self.assertContains(self.client.get("/?sirala=populer"), "Henüz anket yok — ilk kararsızlığı sen paylaş!")


class CopyLinkTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.poll = make_poll(self.user)

    def test_button_is_hidden_until_js_enables_it(self):
        html = self.client.get(f"/anket/{self.poll.pk}/").content.decode()
        self.assertRegex(html, r"<button[^>]*data-copy-link[^>]*\bhidden\b[^>]*>Bağlantıyı kopyala</button>")
        self.assertIn('class="copy-link-status"', html)
        self.assertIn('aria-live="polite"', html)

    def test_script_loaded_whether_or_not_visitor_voted(self):
        before = self.client.get(f"/anket/{self.poll.pk}/")
        self.assertContains(before, "copy_link.js")
        self.client.post(f"/anket/{self.poll.pk}/oy/", {"choice": self.poll.choices.first().pk})
        after = self.client.get(f"/anket/{self.poll.pk}/")
        self.assertContains(after, "copy_link.js")
        self.assertNotContains(after, "vote.js")

    def test_scripts_exist_as_static_files(self):
        for name in ("js/copy_link.js", "js/vote.js", "js/create_poll.js", "img/favicon.svg", "css/style.css"):
            with self.subTest(name=name):
                self.assertIsNotNone(finders.find(name))

    def test_script_uses_clipboard_api_with_clean_url(self):
        source = Path(finders.find("js/copy_link.js")).read_text(encoding="utf-8")
        self.assertIn("navigator.clipboard.writeText", source)
        self.assertIn("location.origin + location.pathname", source)


class MetaTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.poll = make_poll(self.user, 'Hangi "film" izlensin & nerede?', description="gizli açıklama")

    def description(self, url):
        html = self.client.get(url).content.decode()
        match = re.search(r'<meta name="description" content="([^"]*)">', html)
        self.assertIsNotNone(match, f"{url}: meta description yok")
        return match.group(1)

    def test_every_public_page_has_a_description(self):
        for url in ("/", "/?sirala=populer", "/hesap/giris/", "/hesap/kayit/", f"/anket/{self.poll.pk}/", "/kullanici/semih/"):
            with self.subTest(url=url):
                self.assertTrue(len(self.description(url)) > 20)

    def test_detail_description_is_escaped_and_contains_question(self):
        text = self.description(f"/anket/{self.poll.pk}/")
        self.assertIn("film", text)
        self.assertNotIn('"film"', text)  # çift tırnak öznitelikten kaçmamalı
        self.assertIn("&quot;film&quot;", text)
        self.assertIn("&amp;", text)

    def test_long_question_is_truncated_in_description(self):
        poll = make_poll(self.user, "Çok uzun bir soru " * 10)
        self.assertLess(len(self.description(f"/anket/{poll.pk}/")), 220)

    def test_pages_have_favicon_theme_color_and_viewport(self):
        html = self.client.get("/").content.decode()
        self.assertRegex(html, r'<link rel="icon" href="[^"]*favicon[^"]*\.svg" type="image/svg\+xml">')
        self.assertIn('<meta name="theme-color"', html)
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', html)

    def test_every_page_has_a_unique_meaningful_title(self):
        titles = {}
        for url in ("/", "/?sirala=populer", "/hesap/giris/", "/hesap/kayit/", f"/anket/{self.poll.pk}/", "/kullanici/semih/"):
            html = self.client.get(url).content.decode()
            title = re.search(r"<title>([^<]*)</title>", html).group(1)
            self.assertIn("Kararsızım", title, url)
            titles[url] = title
        self.assertEqual(len(set(titles.values())), len(titles))


class ErrorPageTests(TestCase):
    def test_404_page_is_custom_and_turkish(self):
        response = self.client.get("/boyle-bir-sayfa-yok/")
        self.assertContains(response, "Sayfa bulunamadı", status_code=404)
        self.assertContains(response, 'href="/"', status_code=404)
        self.assertContains(response, '<html lang="tr">', status_code=404)

    def test_unknown_poll_and_user_use_the_same_404(self):
        for url in ("/anket/99999/", "/kullanici/yok.boyle.biri/"):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "Sayfa bulunamadı", status_code=404)

    def test_404_does_not_leak_whether_a_poll_exists(self):
        owner, other = make_user("sahip"), make_user("baskasi")
        poll = make_poll(owner)
        self.client.force_login(other)
        existing = self.client.get(f"/anket/{poll.pk}/sil/")
        missing = self.client.get("/anket/99999/sil/")
        self.assertEqual((existing.status_code, missing.status_code), (404, 404))
        strip_csrf = lambda response: re.sub(rb'name="csrfmiddlewaretoken" value="[^"]+"', b"", response.content)
        self.assertEqual(strip_csrf(existing), strip_csrf(missing))

    def test_500_page_is_standalone_and_turkish(self):
        client = Client(raise_request_exception=False)
        with mock.patch("polls.views._poll_queryset", side_effect=RuntimeError("boom")):
            response = client.get("/")
        self.assertEqual(response.status_code, 500)
        html = response.content.decode()
        self.assertIn("Bir şeyler ters gitti", html)
        self.assertIn('<html lang="tr">', html)
        self.assertNotIn("csrfmiddlewaretoken", html)
        self.assertNotIn("{%", html)
        self.assertNotIn("boom", html)  # hata ayrıntısı kullanıcıya sızmaz

    def test_500_template_has_no_template_tags_or_external_assets(self):
        source = (Path(settings.BASE_DIR) / "templates" / "500.html").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"\{%\s*(extends|include|load|static|url)")
        self.assertNotRegex(source, r'(href|src)="https?://')


class AccessibilityTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.poll = make_poll(self.user)

    def pages(self):
        self.client.force_login(self.user)
        return {
            "liste": "/",
            "detay": f"/anket/{self.poll.pk}/",
            "olustur": "/anket/yeni/",
            "sil": f"/anket/{self.poll.pk}/sil/",
            "kullanici": "/kullanici/semih/",
        } | {"giris": "/hesap/giris/", "kayit": "/hesap/kayit/"}

    def test_landmarks_and_skip_link(self):
        for name, url in self.pages().items():
            with self.subTest(page=name):
                client = Client() if name in ("giris", "kayit") else self.client
                html = client.get(url, follow=True).content.decode()
                self.assertIn('<a class="skip-link" href="#icerik">', html)
                self.assertIn('<main class="container" id="icerik">', html)
                self.assertEqual(html.count("<h1"), 1, "sayfada tam bir h1 olmalı")
                self.assertIn('<nav class="header-nav" aria-label="Ana menü">', html)

    def test_every_form_input_has_a_label(self):
        for url in ("/hesap/giris/", "/hesap/kayit/"):
            with self.subTest(url=url):
                html = Client().get(url).content.decode()
                self.assert_inputs_labelled(html)
        self.client.force_login(self.user)
        self.assert_inputs_labelled(self.client.get("/anket/yeni/").content.decode())

    def assert_inputs_labelled(self, html):
        ids = re.findall(r'<(?:input|textarea)(?![^>]*type="hidden")[^>]*\bid="([^"]+)"', html)
        self.assertTrue(ids)
        for field_id in ids:
            self.assertIn(f'for="{field_id}"', html, f"{field_id} için label yok")

    def test_buttons_are_real_buttons_and_images_none(self):
        html = self.client.get(f"/anket/{self.poll.pk}/").content.decode()
        self.assertNotRegex(html, r'<div[^>]*role="button"')
        self.assertNotIn("<img", html)  # alt metni gerektiren görsel yok


def parse_css_colors():
    css = CSS_PATH.read_text(encoding="utf-8")
    return dict(re.findall(r"--color-([a-z-]+):\s*(#[0-9a-fA-F]{6})", css))


def luminance(hex_color):
    channels = [int(hex_color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class ContrastTests(TestCase):
    """WCAG AA: metin ≥ 4.5:1, arayüz öğeleri (kenarlık, çubuk) ≥ 3:1. Renk değişirse test uyarır."""

    def setUp(self):
        self.c = parse_css_colors()
        self.c["white"] = "#ffffff"

    def assert_ratio(self, fg, bg, minimum):
        ratio = contrast(self.c[fg], self.c[bg])
        self.assertGreaterEqual(ratio, minimum, f"{fg} / {bg} = {ratio:.2f}:1 (en az {minimum}:1 olmalı)")

    def test_tokens_were_parsed(self):
        for token in ("bg", "surface", "text", "muted", "primary", "border-strong", "bar", "border"):
            self.assertIn(token, self.c)

    def test_text_contrast(self):
        pairs = [
            ("text", "surface"), ("text", "bg"), ("muted", "surface"), ("muted", "bg"),
            ("primary", "surface"), ("primary", "bg"), ("primary", "primary-soft"),
            ("white", "primary"), ("white", "primary-dark"), ("white", "danger"), ("white", "danger-dark"),
            ("danger-dark", "surface"), ("danger-dark", "danger-bg"),
            ("success-text", "success-bg"), ("primary-dark", "primary-soft"), ("text", "primary-soft"),
        ]
        for fg, bg in pairs:
            with self.subTest(pair=f"{fg}/{bg}"):
                self.assert_ratio(fg, bg, 4.5)

    def test_non_text_contrast(self):
        for fg, bg in [("border-strong", "surface"), ("bar", "border"), ("primary", "border")]:
            with self.subTest(pair=f"{fg}/{bg}"):
                self.assert_ratio(fg, bg, 3.0)

    def test_focus_ring_and_reduced_motion_exist(self):
        css = CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(":focus-visible", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("@media (max-width: 560px)", css)
