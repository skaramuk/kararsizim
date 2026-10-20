from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserModelTests(TestCase):
    def test_email_is_lowercased_and_used_for_login(self):
        user = User.objects.create_user("Ali@Example.com", "ali", "gizli-parola-123")
        self.assertEqual(user.email, "ali@example.com")
        self.assertTrue(self.client.login(username="ali@example.com", password="gizli-parola-123"))

    def test_username_is_unique_case_insensitive(self):
        User.objects.create_user("a@example.com", "Semih", "gizli-parola-123")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("b@example.com", "semih", "gizli-parola-123")

    def test_create_superuser(self):
        admin = User.objects.create_superuser("root@example.com", "root", "gizli-parola-123")
        self.assertTrue(admin.is_staff and admin.is_superuser)


class HomePageTests(TestCase):
    def test_home_page_is_turkish(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="tr">')
        self.assertContains(response, "Kararsızım")
