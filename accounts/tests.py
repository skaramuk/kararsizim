from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

PASSWORD = "gizli-parola-123"


def signup_data(**overrides):
    data = {
        "username": "semih",
        "email": "semih@example.com",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    data.update(overrides)
    return data


class UserModelTests(TestCase):
    def test_email_is_lowercased_and_used_for_login(self):
        user = User.objects.create_user("Ali@Example.com", "ali", PASSWORD)
        self.assertEqual(user.email, "ali@example.com")
        self.assertTrue(self.client.login(username="ali@example.com", password=PASSWORD))

    def test_username_is_unique_case_insensitive(self):
        User.objects.create_user("a@example.com", "Semih", PASSWORD)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("b@example.com", "semih", PASSWORD)

    def test_create_superuser(self):
        admin = User.objects.create_superuser("root@example.com", "root", PASSWORD)
        self.assertTrue(admin.is_staff and admin.is_superuser)


class HomePageTests(TestCase):
    def test_home_page_is_turkish(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="tr">')
        self.assertContains(response, "Kararsızım")


class SignUpTests(TestCase):
    url = "/hesap/kayit/"

    def test_page_renders(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Kayıt ol")
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_successful_signup_logs_in_and_redirects_home(self):
        response = self.client.post(self.url, signup_data(email="Semih@Example.COM"), follow=True)
        self.assertRedirects(response, "/")
        user = User.objects.get(username="semih")
        self.assertEqual(user.email, "semih@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertContains(response, "Hoş geldin, @semih!")

    def test_signup_redirects_to_next(self):
        response = self.client.post(self.url, signup_data() | {"next": "/anket/yeni/"})
        self.assertRedirects(response, "/anket/yeni/", fetch_redirect_response=False)

    def test_signup_ignores_external_next(self):
        response = self.client.post(self.url, signup_data() | {"next": "https://evil.example/"})
        self.assertRedirects(response, "/")

    def test_duplicate_email_rejected_case_insensitive(self):
        User.objects.create_user("semih@example.com", "ilk", PASSWORD)
        response = self.client.post(self.url, signup_data(username="ikinci", email="SEMIH@example.com"))
        self.assertContains(response, "Bu e-posta adresiyle zaten bir hesap var.")
        self.assertFalse(User.objects.filter(username="ikinci").exists())

    def test_username_differing_only_by_case_rejected(self):
        User.objects.create_user("a@example.com", "Semih", PASSWORD)
        response = self.client.post(self.url, signup_data(username="semih", email="b@example.com"))
        self.assertContains(response, "Bu kullanıcı adı zaten alınmış.")
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_usernames_rejected(self):
        for bad in ["ab", "a" * 21, "semih kara", "semih-kara", "şemsi", "ali@x"]:
            with self.subTest(username=bad):
                response = self.client.post(self.url, signup_data(username=bad))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors.get("username"))
                self.assertFalse(User.objects.exists())

    def test_valid_username_characters_accepted(self):
        response = self.client.post(self.url, signup_data(username="Semih_K.99"))
        self.assertRedirects(response, "/")

    def test_reserved_usernames_rejected(self):
        for reserved in ["admin", "Admin", "KARARSIZIM", "kullanici", "api"]:
            with self.subTest(username=reserved):
                response = self.client.post(self.url, signup_data(username=reserved))
                self.assertContains(response, "Bu kullanıcı adı kullanılamaz.")
        self.assertFalse(User.objects.exists())

    def test_password_mismatch_rejected(self):
        response = self.client.post(self.url, signup_data(password2="baska-parola-456"))
        self.assertContains(response, "Parolalar eşleşmiyor.")
        self.assertFalse(User.objects.exists())

    def test_weak_password_rejected(self):
        response = self.client.post(self.url, signup_data(password1="12345678", password2="12345678"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors.get("password2"))
        self.assertFalse(User.objects.exists())

    def test_required_fields_messages_in_turkish(self):
        response = self.client.post(self.url, {})
        self.assertContains(response, "Bu alan zorunludur.")

    def test_logged_in_user_redirected_from_signup(self):
        self.client.force_login(User.objects.create_user("a@example.com", "ali", PASSWORD))
        self.assertRedirects(self.client.get(self.url), "/")


class LoginLogoutTests(TestCase):
    login_url = "/hesap/giris/"
    logout_url = "/hesap/cikis/"

    def setUp(self):
        self.user = User.objects.create_user("semih@example.com", "semih", PASSWORD)

    def test_login_page_labels_email(self):
        response = self.client.get(self.login_url)
        self.assertContains(response, "E-posta")
        self.assertContains(response, "Parola")

    def test_login_success(self):
        response = self.client.post(self.login_url, {"username": "semih@example.com", "password": PASSWORD})
        self.assertRedirects(response, "/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_email_is_case_insensitive(self):
        response = self.client.post(self.login_url, {"username": "Semih@Example.com", "password": PASSWORD})
        self.assertRedirects(response, "/")

    def test_login_with_username_fails(self):
        response = self.client.post(self.login_url, {"username": "semih", "password": PASSWORD})
        self.assertContains(response, "E-posta veya parola hatalı.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_wrong_password(self):
        response = self.client.post(self.login_url, {"username": "semih@example.com", "password": "yanlis"})
        self.assertContains(response, "E-posta veya parola hatalı.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_redirects_to_next(self):
        response = self.client.post(
            self.login_url + "?next=/anket/yeni/",
            {"username": "semih@example.com", "password": PASSWORD, "next": "/anket/yeni/"},
        )
        self.assertRedirects(response, "/anket/yeni/", fetch_redirect_response=False)

    def test_login_ignores_external_next(self):
        response = self.client.post(
            self.login_url,
            {"username": "semih@example.com", "password": PASSWORD, "next": "https://evil.example/"},
        )
        self.assertRedirects(response, "/")

    def test_logged_in_user_redirected_from_login(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(self.login_url), "/")

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.logout_url).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_post_logs_out(self):
        self.client.force_login(self.user)
        response = self.client.post(self.logout_url)
        self.assertRedirects(response, "/")
        self.assertNotIn("_auth_user_id", self.client.session)


class HeaderAndPrivacyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("gizli.adres@example.com", "semih", PASSWORD)

    def test_anonymous_header_links(self):
        response = self.client.get("/")
        self.assertContains(response, 'href="/hesap/giris/"')
        self.assertContains(response, 'href="/hesap/kayit/"')
        self.assertNotContains(response, "Çıkış")

    def test_authenticated_header_links(self):
        self.client.force_login(self.user)
        response = self.client.get("/")
        self.assertContains(response, "@semih")
        self.assertContains(response, 'action="/hesap/cikis/"')
        self.assertNotContains(response, 'href="/hesap/giris/"')
        self.assertNotContains(response, 'href="/hesap/kayit/"')

    def test_email_never_rendered_on_public_pages(self):
        pages = ["/", "/hesap/giris/", "/hesap/kayit/"]
        for logged_in in (False, True):
            if logged_in:
                self.client.force_login(self.user)
            for page in pages:
                with self.subTest(page=page, logged_in=logged_in):
                    follow = self.client.get(page, follow=True)
                    self.assertNotContains(follow, self.user.email)
