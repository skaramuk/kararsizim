import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from . import services
from .models import Choice, Poll, Vote

User = get_user_model()

PASSWORD = "gizli-parola-123"


def make_user(username="semih", email=None):
    return User.objects.create_user(email or f"{username}@example.com", username, PASSWORD)


def make_poll(author, question="Bugün sinemaya mı gitsem?", choices=("Sinema", "Restoran"), **kwargs):
    return services.create_poll(author, question, kwargs.get("description", ""), list(choices))


class PollCreateTests(TestCase):
    url = "/anket/yeni/"

    def setUp(self):
        self.user = make_user()

    def post(self, choices, question="Bugün sinemaya mı gitsem?", **extra):
        data = {"question": question, "description": "", "choices": choices}
        data.update(extra)
        return self.client.post(self.url, data)

    def test_anonymous_redirected_to_login_with_next(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, "/hesap/giris/?next=/anket/yeni/", fetch_redirect_response=False)

    def test_anonymous_post_does_not_create(self):
        self.post(["A", "B"])
        self.assertEqual(Poll.objects.count(), 0)

    def test_form_renders_five_choice_inputs(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, 'name="choices"', count=5)
        self.assertContains(response, "create_poll.js")

    def test_successful_creation(self):
        self.client.force_login(self.user)
        response = self.post(["Sinema", "Restoran", "", "", ""])
        poll = Poll.objects.get()
        self.assertRedirects(response, f"/anket/{poll.pk}/")
        self.assertEqual(poll.author, self.user)
        self.assertEqual(list(poll.choices.values_list("text", "order")), [("Sinema", 0), ("Restoran", 1)])
        follow = self.client.get(f"/anket/{poll.pk}/")
        self.assertEqual(follow.status_code, 200)

    def test_success_message_shown(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, {"question": "Bugün sinemaya mı gitsem?", "choices": ["A", "B"]}, follow=True
        )
        self.assertContains(response, "Anketin yayında!")

    def test_question_is_trimmed_and_blank_choices_ignored(self):
        self.client.force_login(self.user)
        self.post(["  A  ", "", "B", "  ", ""], question="   Hangi renk olsun?   ")
        poll = Poll.objects.get()
        self.assertEqual(poll.question, "Hangi renk olsun?")
        self.assertEqual([c.text for c in poll.choices.all()], ["A", "B"])

    def test_choice_order_follows_submission_order(self):
        self.client.force_login(self.user)
        self.post(["Üçüncü", "Birinci", "İkinci"])
        self.assertEqual([c.text for c in Poll.objects.get().choices.all()], ["Üçüncü", "Birinci", "İkinci"])

    def test_one_choice_rejected(self):
        self.client.force_login(self.user)
        response = self.post(["Sadece biri", "", ""])
        self.assertContains(response, "En az 2 seçenek girmelisin.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_six_choices_rejected(self):
        self.client.force_login(self.user)
        response = self.post(["1", "2", "3", "4", "5", "6"])
        self.assertContains(response, "En fazla 5 seçenek ekleyebilirsin.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_duplicate_choices_rejected_case_insensitive(self):
        self.client.force_login(self.user)
        response = self.post(["Sinema", " sinema ", "Restoran"])
        self.assertContains(response, "Aynı seçeneği birden fazla kez ekleyemezsin.")
        self.assertEqual(Poll.objects.count(), 0)

    def test_too_long_choice_rejected(self):
        self.client.force_login(self.user)
        response = self.post(["A" * 101, "B"])
        self.assertContains(response, "en fazla 100 karakter")
        self.assertEqual(Poll.objects.count(), 0)

    def test_short_question_rejected(self):
        self.client.force_login(self.user)
        response = self.post(["A", "B"], question="Ne?")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors.get("question"))
        self.assertEqual(Poll.objects.count(), 0)

    def test_long_question_and_description_rejected(self):
        self.client.force_login(self.user)
        self.assertEqual(self.post(["A", "B"], question="x" * 201).status_code, 200)
        self.assertEqual(self.post(["A", "B"], description="x" * 501).status_code, 200)
        self.assertEqual(Poll.objects.count(), 0)

    def test_invalid_form_keeps_entered_choices(self):
        self.client.force_login(self.user)
        response = self.post(["Sinema", "", "Restoran"], question="Ne?")
        self.assertContains(response, 'value="Sinema"')
        self.assertContains(response, 'value="Restoran"')


class ServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_service_enforces_choice_limits(self):
        for bad in (["A"], ["1", "2", "3", "4", "5", "6"], ["A", "a"]):
            with self.subTest(choices=bad), self.assertRaises(ValidationError):
                services.create_poll(self.user, "Geçerli bir soru", "", bad)
        self.assertEqual(Poll.objects.count(), 0)

    def test_service_validates_question(self):
        with self.assertRaises(ValidationError):
            services.create_poll(self.user, "Ne?", "", ["A", "B"])
        self.assertEqual(Poll.objects.count(), 0)

    def test_failed_choice_insert_rolls_back_poll(self):
        original = Choice.objects.bulk_create

        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        Choice.objects.bulk_create = boom
        try:
            with self.assertRaises(RuntimeError):
                services.create_poll(self.user, "Geçerli bir soru", "", ["A", "B"])
        finally:
            Choice.objects.bulk_create = original
        self.assertEqual(Poll.objects.count(), 0)


class PollListTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_empty_state(self):
        response = self.client.get("/")
        self.assertContains(response, "Henüz anket yok — ilk kararsızlığı sen paylaş!")

    def test_anonymous_sees_list_newest_first(self):
        old = make_poll(self.user, "Eski anket sorusu")
        new = make_poll(self.user, "Yeni anket sorusu")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"]), [new, old])
        self.assertContains(response, "@semih")
        self.assertContains(response, "2 seçenek")
        self.assertContains(response, "0 oy")

    def test_card_shows_vote_count(self):
        poll = make_poll(self.user)
        choice = poll.choices.first()
        for _ in range(3):
            Vote.objects.create(poll=poll, choice=choice, voter_token=uuid.uuid4())
        response = self.client.get("/")
        self.assertContains(response, "3 oy")
        self.assertEqual(response.context["page_obj"][0].vote_count, 3)
        self.assertEqual(response.context["page_obj"][0].choice_count, 2)

    def test_pagination(self):
        for index in range(25):
            make_poll(self.user, f"Soru numarası {index:02d}")
        first = self.client.get("/")
        self.assertEqual(len(first.context["page_obj"]), 20)
        self.assertContains(first, "Sayfa 1 / 2")
        second = self.client.get("/?page=2")
        self.assertEqual(len(second.context["page_obj"]), 5)
        self.assertEqual(self.client.get("/?page=999").status_code, 200)
        self.assertEqual(self.client.get("/?page=abc").status_code, 200)

    def test_no_n_plus_one_queries(self):
        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                self.client.get("/")
            return len(ctx)

        make_poll(self.user)
        baseline = count_queries()
        for index in range(10):
            make_poll(make_user(f"yazar{index}"), f"Başka bir soru {index}")
        self.assertEqual(count_queries(), baseline)

    def test_question_is_escaped(self):
        make_poll(self.user, "<script>alert(1)</script> tehlikeli mi")
        response = self.client.get("/")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")


class PollDetailTests(TestCase):
    def setUp(self):
        self.owner = make_user("sahip")
        self.poll = make_poll(self.owner, "Hangi filmi izleyelim?", ["Film A", "Film B", "Film C"], description="Akşam için\nönerilere açığım")

    def test_anonymous_can_view(self):
        response = self.client.get(f"/anket/{self.poll.pk}/")
        self.assertEqual(response.status_code, 200)
        for text in ("Hangi filmi izleyelim?", "Film A", "Film B", "Film C", "@sahip", "Akşam için", "önerilere açığım"):
            self.assertContains(response, text)
        self.assertNotContains(response, "Anketi sil")

    def test_owner_sees_delete_link(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(f"/anket/{self.poll.pk}/"), "Anketi sil")

    def test_other_user_does_not_see_delete_link(self):
        self.client.force_login(make_user("baskasi"))
        self.assertNotContains(self.client.get(f"/anket/{self.poll.pk}/"), "Anketi sil")

    def test_missing_poll_404(self):
        self.assertEqual(self.client.get("/anket/99999/").status_code, 404)


class PollDeleteTests(TestCase):
    def setUp(self):
        self.owner = make_user("sahip")
        self.other = make_user("baskasi")
        self.poll = make_poll(self.owner)
        self.url = f"/anket/{self.poll.pk}/sil/"

    def test_owner_get_shows_confirmation(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertContains(response, "silmek istediğine emin misin")
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_owner_post_deletes_with_choices_and_votes(self):
        Vote.objects.create(poll=self.poll, choice=self.poll.choices.first(), voter_token=uuid.uuid4())
        self.client.force_login(self.owner)
        response = self.client.post(self.url, follow=True)
        self.assertRedirects(response, "/")
        self.assertContains(response, "Anket silindi.")
        self.assertEqual((Poll.objects.count(), Choice.objects.count(), Vote.objects.count()), (0, 0, 0))

    def test_non_owner_gets_404_and_cannot_delete(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_anonymous_cannot_delete(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/hesap/giris/", response["Location"])
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_missing_poll_404(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/anket/99999/sil/").status_code, 404)


class UserPollsTests(TestCase):
    def setUp(self):
        self.user = make_user("Semih", email="gizli.adres@example.com")
        self.other = make_user("diger")
        self.mine = make_poll(self.user, "Benim anketim burada")
        self.theirs = make_poll(self.other, "Başkasının anketi burada")

    def test_shows_only_that_users_polls(self):
        response = self.client.get("/kullanici/Semih/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"]), [self.mine])
        self.assertContains(response, "@Semih")
        self.assertNotContains(response, "Başkasının anketi burada")

    def test_username_lookup_is_case_insensitive(self):
        self.assertEqual(self.client.get("/kullanici/semih/").status_code, 200)

    def test_unknown_user_404(self):
        self.assertEqual(self.client.get("/kullanici/yok.boyle.biri/").status_code, 404)

    def test_empty_state(self):
        make_user("sessiz")
        self.assertContains(self.client.get("/kullanici/sessiz/"), "henüz anket paylaşmadı")

    def test_email_not_leaked_on_public_pages(self):
        self.client.force_login(self.other)
        pages = ["/", "/kullanici/Semih/", f"/anket/{self.mine.pk}/"]
        for logged_in in (False, True):
            if not logged_in:
                self.client.logout()
            for page in pages:
                with self.subTest(page=page, logged_in=logged_in):
                    response = self.client.get(page)
                    self.assertNotContains(response, "gizli.adres@example.com")
                    self.assertNotContains(response, "diger@example.com")

    def test_header_links_to_own_page(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get("/"), 'href="/kullanici/Semih/"')


class VoteConstraintTests(TestCase):
    """Vote modelinin veritabanı kısıtları (oy verme mantığı Faz 3'te)."""

    def setUp(self):
        self.user = make_user()
        self.poll = make_poll(self.user)
        self.choice = self.poll.choices.first()

    def test_one_vote_per_user_per_poll(self):
        Vote.objects.create(poll=self.poll, choice=self.choice, user=self.user, voter_token=uuid.uuid4())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vote.objects.create(poll=self.poll, choice=self.choice, user=self.user, voter_token=uuid.uuid4())

    def test_one_vote_per_token_per_poll(self):
        token = uuid.uuid4()
        Vote.objects.create(poll=self.poll, choice=self.choice, voter_token=token)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vote.objects.create(poll=self.poll, choice=self.choice, voter_token=token)

    def test_same_token_may_vote_in_different_polls(self):
        token = uuid.uuid4()
        other_poll = make_poll(self.user, "Bir başka soru burada")
        Vote.objects.create(poll=self.poll, choice=self.choice, voter_token=token)
        Vote.objects.create(poll=other_poll, choice=other_poll.choices.first(), voter_token=token)
        self.assertEqual(Vote.objects.count(), 2)

    def test_vote_needs_user_or_token(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vote.objects.create(poll=self.poll, choice=self.choice)

    def test_vote_survives_user_deletion(self):
        voter = make_user("oyveren")
        Vote.objects.create(poll=self.poll, choice=self.choice, user=voter, voter_token=uuid.uuid4())
        voter.delete()
        vote = Vote.objects.get()
        self.assertIsNone(vote.user)
        self.assertIsNotNone(vote.voter_token)
