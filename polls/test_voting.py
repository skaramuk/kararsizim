"""Faz 3: oylama, çerezler, sonuçların görünürlüğü ve JSON yanıtları."""

import uuid
from unittest import mock

from django.db import connection
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from . import services, voter
from .models import Vote
from .tests import make_poll, make_user


def vote_url(poll):
    return f"/anket/{poll.pk}/oy/"


class VoteTestCase(TestCase):
    def setUp(self):
        self.owner = make_user("sahip", email="sahip.gizli@example.com")
        self.poll = make_poll(self.owner, "Hafta sonu ne yapalım?", ["Sinema", "Restoran", "Yürüyüş"])
        self.sinema, self.restoran, self.yuruyus = self.poll.choices.all()

    def vote(self, choice, poll=None, client=None, json_response=False, **extra):
        client = client or self.client
        if json_response:
            extra["HTTP_ACCEPT"] = "application/json"
        value = choice.pk if hasattr(choice, "pk") else choice
        return client.post(vote_url(poll or self.poll), {"choice": value}, **extra)


class AnonymousVoteTests(VoteTestCase):
    def test_vote_sets_signed_httponly_cookie_and_saves_token(self):
        response = self.vote(self.sinema)
        self.assertRedirects(response, f"/anket/{self.poll.pk}/", fetch_redirect_response=False)
        cookie = response.cookies[voter.COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(int(cookie["max-age"]), 60 * 60 * 24 * 365)

        vote = Vote.objects.get()
        self.assertEqual(vote.choice, self.sinema)
        self.assertIsNone(vote.user)
        self.assertIsNotNone(vote.voter_token)
        # Çerez imzalı: değer ham UUID değil, UUID'yi ve imzayı birlikte taşır.
        self.assertNotEqual(cookie.value, str(vote.voter_token))
        self.assertIn(str(vote.voter_token), cookie.value)

    def test_ip_is_stored_only_as_hash(self):
        self.vote(self.sinema, REMOTE_ADDR="203.0.113.7")
        vote = Vote.objects.get()
        self.assertEqual(len(vote.ip_hash), 64)
        self.assertNotIn("203.0.113.7", vote.ip_hash)

    def test_ip_hash_uses_first_forwarded_address(self):
        self.vote(self.sinema, HTTP_X_FORWARDED_FOR="198.51.100.9, 10.0.0.1", REMOTE_ADDR="10.0.0.1")
        forwarded = Vote.objects.get().ip_hash
        Vote.objects.all().delete()
        self.vote(self.sinema, client=Client(), REMOTE_ADDR="198.51.100.9")
        self.assertEqual(Vote.objects.get().ip_hash, forwarded)

    def test_second_vote_with_same_cookie_rejected(self):
        self.vote(self.sinema)
        response = self.vote(self.restoran, follow=True)
        self.assertContains(response, "Bu ankete zaten oy verdin.")
        self.assertEqual(Vote.objects.count(), 1)
        self.assertEqual(Vote.objects.get().choice, self.sinema)

    def test_second_vote_json_returns_409(self):
        self.vote(self.sinema, json_response=True)
        response = self.vote(self.restoran, json_response=True)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"ok": False, "error": "Bu ankete zaten oy verdin."})

    def test_existing_cookie_is_reused_not_reissued(self):
        first = self.vote(self.sinema)
        other = make_poll(self.owner, "Başka bir anket sorusu", ["A", "B"])
        second = self.vote(other.choices.first(), poll=other)
        self.assertIn(voter.COOKIE_NAME, first.cookies)
        self.assertNotIn(voter.COOKIE_NAME, second.cookies)
        self.assertEqual(Vote.objects.values("voter_token").distinct().count(), 1)

    def test_different_visitors_can_each_vote(self):
        self.vote(self.sinema)
        self.vote(self.sinema, client=Client())
        self.assertEqual(Vote.objects.count(), 2)

    def test_unsigned_cookie_is_ignored_and_replaced(self):
        self.client.cookies[voter.COOKIE_NAME] = str(uuid.uuid4())
        response = self.vote(self.sinema)
        self.assertEqual(Vote.objects.count(), 1)
        self.assertIn(voter.COOKIE_NAME, response.cookies)

    def test_garbage_cookie_does_not_crash(self):
        for garbage in ("cop:deger:imza", "not-a-uuid", ":::", "x" * 500):
            with self.subTest(cookie=garbage[:20]):
                client = Client()
                client.cookies[voter.COOKIE_NAME] = garbage
                self.assertEqual(self.vote(self.sinema, client=client).status_code, 302)
        self.assertEqual(Vote.objects.count(), 4)

    def test_deleting_cookie_allows_new_vote_known_limitation(self):
        self.vote(self.sinema)
        self.client.cookies.clear()
        self.vote(self.restoran)
        self.assertEqual(Vote.objects.count(), 2)


class MemberVoteTests(VoteTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_user("uye")
        self.client.force_login(self.member)

    def test_member_vote_stores_user_and_token(self):
        self.vote(self.restoran)
        vote = Vote.objects.get()
        self.assertEqual(vote.user, self.member)
        self.assertIsNotNone(vote.voter_token)

    def test_member_cannot_vote_twice(self):
        self.vote(self.restoran)
        response = self.vote(self.sinema, json_response=True)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Vote.objects.count(), 1)

    def test_member_cannot_vote_twice_after_cookie_lost(self):
        self.vote(self.restoran)
        self.client.cookies.pop(voter.COOKIE_NAME)
        response = self.vote(self.sinema, json_response=True)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Vote.objects.count(), 1)

    def test_member_vote_counts_across_browsers(self):
        self.vote(self.restoran)
        other_browser = Client()
        other_browser.force_login(self.member)
        response = self.vote(self.sinema, client=other_browser, json_response=True)
        self.assertEqual(response.status_code, 409)

    def test_owner_can_vote_on_own_poll(self):
        client = Client()
        client.force_login(self.owner)
        self.assertEqual(self.vote(self.sinema, client=client).status_code, 302)
        self.assertEqual(Vote.objects.get().user, self.owner)

    def test_race_is_caught_by_database_constraint(self):
        self.vote(self.restoran)
        with mock.patch("polls.services.get_user_vote", return_value=None):
            response = self.vote(self.sinema, json_response=True)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Vote.objects.count(), 1)


class InvalidVoteTests(VoteTestCase):
    def test_choice_from_another_poll_returns_400(self):
        other = make_poll(self.owner, "Başka bir anket sorusu", ["X", "Y"])
        foreign = other.choices.first()
        self.assertEqual(self.vote(foreign).status_code, 400)
        self.assertEqual(self.vote(foreign, json_response=True).status_code, 400)
        self.assertEqual(Vote.objects.count(), 0)

    def test_json_error_body(self):
        response = self.vote(999999, json_response=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"ok": False, "error": "Geçersiz seçenek."})

    def test_missing_or_non_numeric_choice_returns_400(self):
        self.assertEqual(self.client.post(vote_url(self.poll), {}).status_code, 400)
        self.assertEqual(self.vote("abc").status_code, 400)
        self.assertEqual(self.vote("-1").status_code, 400)
        self.assertEqual(Vote.objects.count(), 0)

    def test_missing_choice_form_shows_message(self):
        response = self.client.post(vote_url(self.poll), {})
        self.assertContains(response, "Bir seçenek seçmelisin.", status_code=400)

    def test_invalid_vote_does_not_set_cookie(self):
        self.assertNotIn(voter.COOKIE_NAME, self.vote(999999).cookies)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(vote_url(self.poll)).status_code, 405)

    def test_unknown_poll_404(self):
        self.assertEqual(self.client.post("/anket/99999/oy/", {"choice": 1}).status_code, 404)

    def test_csrf_enforced(self):
        strict = Client(enforce_csrf_checks=True)
        response = strict.post(vote_url(self.poll), {"choice": self.sinema.pk})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Vote.objects.count(), 0)


class VoteJsonTests(VoteTestCase):
    def test_json_success_shape(self):
        Vote.objects.create(poll=self.poll, choice=self.restoran, voter_token=uuid.uuid4())
        response = self.vote(self.sinema, json_response=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "ok": True,
                "total": 2,
                "voted_choice_id": self.sinema.pk,
                "results": [
                    {"id": self.sinema.pk, "text": "Sinema", "count": 1, "percent": 50},
                    {"id": self.restoran.pk, "text": "Restoran", "count": 1, "percent": 50},
                    {"id": self.yuruyus.pk, "text": "Yürüyüş", "count": 0, "percent": 0},
                ],
            },
        )
        self.assertIn(voter.COOKIE_NAME, response.cookies)

    def test_json_never_contains_emails(self):
        member = make_user("uye", email="uye.gizli@example.com")
        self.client.force_login(member)
        response = self.vote(self.sinema, json_response=True)
        body = response.content.decode()
        for email in ("uye.gizli@example.com", "sahip.gizli@example.com"):
            self.assertNotIn(email, body)
        self.assertEqual(set(response.json()), {"ok", "total", "voted_choice_id", "results"})

    def test_form_post_redirects_with_message(self):
        response = self.vote(self.sinema, follow=True)
        self.assertRedirects(response, f"/anket/{self.poll.pk}/")
        self.assertContains(response, "Oyun kaydedildi.")


class ResultsTests(VoteTestCase):
    def add_votes(self, choice, count):
        for _ in range(count):
            Vote.objects.create(poll=self.poll, choice=choice, voter_token=uuid.uuid4())

    def test_percentages_are_rounded_integers(self):
        self.add_votes(self.sinema, 1)
        self.add_votes(self.restoran, 2)
        results = services.get_results(self.poll)
        self.assertEqual(results["total"], 3)
        self.assertEqual([r["percent"] for r in results["results"]], [33, 67, 0])
        self.assertEqual([r["count"] for r in results["results"]], [1, 2, 0])

    def test_no_votes_gives_zero_percent(self):
        results = services.get_results(self.poll)
        self.assertEqual(results["total"], 0)
        self.assertEqual({r["percent"] for r in results["results"]}, {0})

    def test_results_follow_choice_order(self):
        results = services.get_results(self.poll)
        self.assertEqual([r["text"] for r in results["results"]], ["Sinema", "Restoran", "Yürüyüş"])

    def test_non_voter_sees_buttons_not_results(self):
        self.add_votes(self.sinema, 3)
        response = self.client.get(f"/anket/{self.poll.pk}/")
        self.assertContains(response, 'name="choice"', count=3)
        self.assertContains(response, "vote.js")
        self.assertNotContains(response, "result-fill")
        self.assertNotContains(response, "Toplam 3 oy")
        self.assertNotContains(response, "%100")

    def test_voter_sees_results_and_own_choice_highlighted(self):
        self.add_votes(self.sinema, 2)
        self.vote(self.restoran)
        response = self.client.get(f"/anket/{self.poll.pk}/")
        self.assertContains(response, "Toplam 3 oy")
        self.assertContains(response, "2 oy · %67")
        self.assertContains(response, "1 oy · %33")
        self.assertContains(response, "✓ Senin oyun", count=1)
        self.assertContains(response, "is-mine", count=1)
        self.assertNotContains(response, 'name="choice"')
        self.assertNotContains(response, "vote.js")

    def test_owner_always_sees_results_and_can_still_vote(self):
        self.add_votes(self.sinema, 1)
        self.client.force_login(self.owner)
        response = self.client.get(f"/anket/{self.poll.pk}/")
        self.assertContains(response, "Toplam 1 oy")
        self.assertContains(response, "%100")
        self.assertContains(response, 'name="choice"', count=3)
        self.assertNotContains(response, "✓ Senin oyun")

    def test_owner_after_voting_sees_highlight_and_no_form(self):
        self.client.force_login(self.owner)
        self.vote(self.yuruyus)
        response = self.client.get(f"/anket/{self.poll.pk}/")
        self.assertContains(response, "✓ Senin oyun", count=1)
        self.assertNotContains(response, 'name="choice"')

    def test_other_member_does_not_see_results_before_voting(self):
        self.add_votes(self.sinema, 2)
        self.client.force_login(make_user("gozlemci"))
        response = self.client.get(f"/anket/{self.poll.pk}/")
        self.assertNotContains(response, "Toplam 2 oy")
        self.assertContains(response, 'name="choice"', count=3)

    def test_owner_email_not_rendered_on_detail(self):
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(f"/anket/{self.poll.pk}/"), "sahip.gizli@example.com")


class VotedBadgeTests(VoteTestCase):
    def test_badge_only_on_voted_polls_for_anonymous(self):
        other = make_poll(self.owner, "Oy vermediğim anket", ["A", "B"])
        self.vote(self.sinema)
        response = self.client.get("/")
        self.assertContains(response, "Oy verdin ✓", count=1)
        self.assertEqual(response.context["voted_poll_ids"], {self.poll.pk})
        self.assertNotIn(other.pk, response.context["voted_poll_ids"])

    def test_badge_for_member_and_on_user_page(self):
        self.client.force_login(make_user("uye"))
        self.vote(self.sinema)
        self.assertContains(self.client.get("/"), "Oy verdin ✓", count=1)
        self.assertContains(self.client.get("/kullanici/sahip/"), "Oy verdin ✓", count=1)

    def test_no_badge_for_fresh_visitor(self):
        self.vote(self.sinema)
        self.assertNotContains(Client().get("/"), "Oy verdin ✓")

    def test_vote_lookup_does_not_grow_with_poll_count(self):
        self.client.force_login(make_user("uye"))

        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                self.client.get("/")
            return len(ctx)

        baseline = count_queries()
        for index in range(12):
            make_poll(self.owner, f"Yeni bir anket sorusu {index}")
        self.assertEqual(count_queries(), baseline)


class VoterHelperTests(TestCase):
    def test_token_roundtrip(self):
        token = uuid.uuid4()
        request = RequestFactory().get("/")
        response = HttpResponse()
        voter.set_voter_cookie(request, response, token)
        request.COOKIES[voter.COOKIE_NAME] = response.cookies[voter.COOKIE_NAME].value
        self.assertEqual(voter.get_voter_token(request), token)

    def test_secure_flag_follows_request_scheme(self):
        response = HttpResponse()
        voter.set_voter_cookie(RequestFactory().get("/", secure=True), response, uuid.uuid4())
        self.assertTrue(response.cookies[voter.COOKIE_NAME]["secure"])
        response = HttpResponse()
        voter.set_voter_cookie(RequestFactory().get("/"), response, uuid.uuid4())
        self.assertFalse(response.cookies[voter.COOKIE_NAME]["secure"])

    def test_cast_vote_requires_an_identity(self):
        owner = make_user()
        poll = make_poll(owner)
        with self.assertRaises(ValueError):
            services.cast_vote(poll, poll.choices.first().pk, None, None)
