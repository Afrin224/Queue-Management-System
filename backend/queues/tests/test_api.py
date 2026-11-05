import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.conf import settings
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings

from queues import services
from queues.models import Manager, Queue, RateLimit, Token, timestamp_ms


class APIClientMixin:
    def post(self, path, data=None, client=None, **extra):
        return (client or self.client).post(path, json.dumps({} if data is None else data), content_type="application/json", **extra)

    def make_queue(self, name="General reception", client=None):
        response = self.post("/api/queues", {"name": name}, client)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["queue"]

    def add(self, queue, name="Olivia Bennett", client=None):
        response = self.post(f"/api/queues/{queue['id']}/tokens", {"name": name}, client)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["token"]

    def detail(self, queue):
        return self.client.get(f"/api/queues/{queue['id']}").json()

    def call_next(self, queue):
        return self.post(f"/api/queues/{queue['id']}/serve-next", {"revision": self.detail(queue)["queue"]["revision"]})


class APITests(APIClientMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = Manager.objects.create_user("alex@example.com", "CorrectHorse42!", name="Alex Morgan")
        cls.other = Manager.objects.create_user("blair@example.com", "AnotherPassword42!", name="Blair Lee")

    def setUp(self):
        self.client.force_login(self.manager)

    def test_public_config_and_index_supply_csrf_cookie(self):
        client = Client(enforce_csrf_checks=True)
        self.assertContains(client.get("/"), "Queueflow")
        self.assertIn("csrftoken", client.cookies)
        self.assertEqual(client.get("/api/config").json()["backend"], "django")
        self.assertEqual(client.get("/api/health").json()["status"], "ok")

    def test_security_headers_and_static_assets(self):
        response = self.client.get("/")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
        self.assertEqual(self.client.get("/styles.css").status_code, 200)
        self.assertEqual(self.client.get("/app.js").status_code, 200)
        self.assertEqual(self.client.get("/server/index.js").status_code, 404)

    def test_private_routes_require_login(self):
        client = Client()
        for path in ["/api/auth/me", "/api/queues", "/api/analytics", "/api/activity"]:
            self.assertEqual(client.get(path).status_code, 401)

    def test_register_login_and_logout_with_rotating_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/api/config")
        initial_csrf = client.cookies["csrftoken"].value
        data = {"name": "Casey", "email": "casey@example.com", "password": "Password123!"}
        self.assertEqual(self.post("/api/auth/register", data, client).status_code, 403)
        response = self.post("/api/auth/register", data, client, HTTP_X_CSRFTOKEN=initial_csrf)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertNotIn("password", response.json()["user"])
        self.assertNotEqual(client.cookies["csrftoken"].value, initial_csrf)
        self.assertTrue(client.cookies[settings.SESSION_COOKIE_NAME]["httponly"])
        self.assertEqual(client.get("/api/auth/me").json()["user"]["name"], "Casey")
        csrf = client.cookies["csrftoken"].value
        self.assertEqual(self.post("/api/auth/logout", {}, client, HTTP_X_CSRFTOKEN=csrf).status_code, 200)
        self.assertEqual(client.get("/api/auth/me").status_code, 401)
        response = self.post("/api/auth/login", {"email": "CASEY@example.com", "password": "Password123!"}, client, HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(client.cookies["csrftoken"].value, csrf)

    def test_duplicate_registration_is_case_insensitive(self):
        response = self.post("/api/auth/register", {"name": "Alex", "email": "ALEX@example.com", "password": "Password123!"}, Client())
        self.assertEqual(response.status_code, 409)

    def test_invalid_registration(self):
        for data in [
            {"name": "", "email": "valid@example.com", "password": "Password123!"},
            {"name": "Name", "email": "invalid", "password": "Password123!"},
            {"name": "Name", "email": "valid@example.com", "password": "short"},
            {"name": "Name", "email": "valid@example.com", "password": 12345678},
        ]:
            self.assertEqual(self.post("/api/auth/register", data, Client()).status_code, 400)

    def test_incorrect_password_and_nonexistent_account(self):
        for email in ["alex@example.com", "missing@example.com"]:
            self.assertEqual(self.post("/api/auth/login", {"email": email, "password": "IncorrectPassword"}, Client()).status_code, 401)

    def test_cross_origin_and_missing_csrf_are_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        client.get("/api/config")
        csrf = client.cookies["csrftoken"].value
        self.assertEqual(self.post("/api/queues", {"name": "No csrf"}, client).status_code, 403)
        self.assertEqual(self.post("/api/queues", {"name": "Cross origin"}, client, HTTP_X_CSRFTOKEN=csrf, HTTP_ORIGIN="https://attacker.example").status_code, 403)
        self.assertEqual(self.post("/api/queues", {"name": "Valid"}, client, HTTP_X_CSRFTOKEN=csrf).status_code, 201)

    def test_queue_creation_and_validation(self):
        queue = self.make_queue()
        self.assertEqual(queue["prefix"], "GR")
        self.assertEqual(queue["name"], "General reception")
        for name in [" ", "x" * 61, 123]:
            self.assertEqual(self.post("/api/queues", {"name": name}).status_code, 400)

    def test_ownership_on_all_operations(self):
        queue = self.make_queue()
        token = self.add(queue)
        client = Client()
        client.force_login(self.other)
        for path in [f"/api/queues/{queue['id']}", f"/api/analytics?queueId={queue['id']}", f"/api/activity?queueId={queue['id']}"]:
            self.assertEqual(client.get(path).status_code, 404)
        for suffix, body in [("tokens", {"name": "Intruder"}), ("serve-next", {"revision": 1}), (f"tokens/{token['id']}/move", {"direction": "up", "revision": 1}), (f"tokens/{token['id']}/cancel", {}), (f"tokens/{token['id']}/complete", {})]:
            self.assertEqual(self.post(f"/api/queues/{queue['id']}/{suffix}", body, client).status_code, 404)
        response = client.patch(f"/api/queues/{queue['id']}", json.dumps({"paused": True, "revision": 1}), content_type="application/json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(client.get("/api/queues").json()["queues"], [])

    def test_tokens_are_sequential_and_never_reused(self):
        queue = self.make_queue()
        one = self.add(queue, "First")
        two = self.add(queue, "Second")
        self.assertEqual([one["number"], two["number"]], [1, 2])
        self.post(f"/api/queues/{queue['id']}/tokens/{one['id']}/cancel")
        self.assertEqual(self.add(queue, "Third")["number"], 3)
        self.assertEqual([t["name"] for t in self.detail(queue)["waiting"]], ["Second", "Third"])

    def test_reordering_preserves_numbers_and_rejects_stale_revisions(self):
        queue = self.make_queue()
        one, two = self.add(queue, "First"), self.add(queue, "Second")
        revision = self.detail(queue)["queue"]["revision"]
        path = f"/api/queues/{queue['id']}/tokens/{two['id']}/move"
        self.assertEqual(self.post(path, {"direction": "up", "revision": revision}).status_code, 200)
        self.assertEqual([t["number"] for t in self.detail(queue)["waiting"]], [2, 1])
        self.assertEqual(self.post(path, {"direction": "down", "revision": revision}).status_code, 409)
        revision = self.detail(queue)["queue"]["revision"]
        self.assertEqual(self.post(path, {"direction": "down", "revision": revision}).status_code, 200)
        self.assertEqual(self.detail(queue)["waiting"][0]["id"], one["id"])

    def test_invalid_moves_and_queue_revision(self):
        queue = self.make_queue()
        token = self.add(queue)
        path = f"/api/queues/{queue['id']}/tokens/{token['id']}/move"
        for direction, status in [("up", 409), ("down", 409), ("sideways", 400)]:
            self.assertEqual(self.post(path, {"direction": direction, "revision": 1}).status_code, status)
        self.assertEqual(self.post(f"/api/queues/{queue['id']}/serve-next").status_code, 400)
        self.assertEqual(self.post(f"/api/queues/{queue['id']}/serve-next", {"revision": True}).status_code, 400)

    def test_call_next_assigns_top_and_requires_completion(self):
        queue = self.make_queue()
        one, two = self.add(queue, "First"), self.add(queue, "Second")
        self.post(f"/api/queues/{queue['id']}/tokens/{two['id']}/move", {"direction": "up", "revision": 2})
        response = self.call_next(queue)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"]["id"], two["id"])
        self.assertEqual(self.call_next(queue).status_code, 409)
        self.assertEqual(self.post(f"/api/queues/{queue['id']}/tokens/{two['id']}/complete").status_code, 200)
        self.assertEqual(self.call_next(queue).json()["token"]["id"], one["id"])

    def test_cancellation_preserves_record_and_invalid_transitions_fail(self):
        queue = self.make_queue()
        token = self.add(queue)
        path = f"/api/queues/{queue['id']}/tokens/{token['id']}"
        self.assertEqual(self.post(path + "/complete").status_code, 409)
        self.assertEqual(self.post(path + "/cancel").status_code, 200)
        self.assertEqual(self.post(path + "/cancel").status_code, 409)
        self.assertEqual(self.call_next(queue).status_code, 409)
        self.assertEqual(self.client.get("/api/activity").json()["activity"][0]["status"], "cancelled")

    def test_cannot_cancel_serving_or_completed_tokens(self):
        queue = self.make_queue()
        token = self.add(queue)
        self.call_next(queue)
        path = f"/api/queues/{queue['id']}/tokens/{token['id']}"
        self.assertEqual(self.post(path + "/cancel").status_code, 409)
        self.assertEqual(self.post(path + "/complete").status_code, 200)
        self.assertEqual(self.post(path + "/complete").status_code, 409)

    def test_pausing_blocks_arrival_and_service_but_allows_completion(self):
        queue = self.make_queue()
        token = self.add(queue)
        self.add(queue, "Second")
        self.call_next(queue)
        url = f"/api/queues/{queue['id']}"
        def pause(value):
            revision = self.detail(queue)["queue"]["revision"]
            return self.client.patch(url, json.dumps({"paused": value, "revision": revision}), content_type="application/json")
        self.assertEqual(pause(True).status_code, 200)
        self.assertEqual(self.post(url + "/tokens", {"name": "Third"}).status_code, 409)
        self.assertEqual(self.post(url + f"/tokens/{token['id']}/complete").status_code, 200)
        self.assertEqual(self.call_next(queue).status_code, 409)
        self.assertEqual(pause(False).status_code, 200)
        self.assertEqual(self.call_next(queue).status_code, 200)

    def test_analytics_with_known_durations(self):
        queue = Queue.objects.create(manager=self.manager, name="Analytics", prefix="A")
        now = timestamp_ms()
        Token.objects.create(queue=queue, number=1, name="Done", position=1, status="completed", created_at=now - 30 * 60_000, started_at=now - 20 * 60_000, ended_at=now - 15 * 60_000)
        Token.objects.create(queue=queue, number=2, name="Waiting", position=2, created_at=now - 12 * 60_000)
        Token.objects.create(queue=queue, number=3, name="Cancelled", position=3, status="cancelled", created_at=now - 25 * 60_000, ended_at=now - 10 * 60_000)
        data = self.client.get(f"/api/analytics?days=7&queueId={queue.id}&offset=-330").json()
        self.assertEqual((data["averageWait"], data["averageService"]), (10, 5))
        self.assertEqual((data["waiting"], data["completed"], data["cancelled"], data["arrivals"]), (1, 1, 1, 3))
        self.assertEqual(data["points"][-1]["queueLength"], 1)
        self.assertEqual(data["points"][0]["at"] % 86_400_000, 66_600_000)

    def test_empty_metrics_and_invalid_reporting_parameters(self):
        data = self.client.get("/api/analytics").json()
        self.assertIsNone(data["averageWait"])
        self.assertEqual(data["waiting"], 0)
        for query in ["days=2", "days=no", "offset=9999", "offset=2.5", "queueId=invalid"]:
            self.assertIn(self.client.get("/api/analytics?" + query).status_code, [400, 404])

    def test_activity_pagination_includes_equal_timestamps(self):
        queue = Queue.objects.create(manager=self.manager, name="Pages", prefix="P")
        now = timestamp_ms()
        Token.objects.bulk_create([Token(queue=queue, number=i, name=f"Visitor {i}", position=i, created_at=now) for i in range(1, 106)])
        first = self.client.get("/api/activity").json()["activity"]
        last = first[-1]
        second = self.client.get(f"/api/activity?before={last['event_at']}&beforeId={last['id']}").json()["activity"]
        self.assertEqual((len(first), len(second)), (100, 5))
        self.assertEqual(len({row["id"] for row in first + second}), 105)

    def test_body_validation_and_missing_routes(self):
        self.assertEqual(self.post("/api/queues", []).status_code, 400)
        self.assertEqual(self.client.post("/api/queues", "{bad", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/api/queues", "name=x", content_type="text/plain").status_code, 415)
        self.assertEqual(self.post("/api/queues", {"name": "x" * 17_000}).status_code, 413)
        self.assertEqual(self.client.delete("/api/queues").status_code, 405)
        self.assertEqual(self.client.get("/api/missing").status_code, 404)

    @override_settings(ENABLE_DEMO=True)
    def test_demo_is_isolated_and_fully_populated(self):
        first, second = Client(), Client()
        one = self.post("/api/auth/demo", client=first)
        two = self.post("/api/auth/demo", client=second)
        self.assertEqual(one.status_code, 201)
        self.assertNotEqual(one.json()["user"]["id"], two.json()["user"]["id"])
        queues = first.get("/api/queues").json()["queues"]
        self.assertEqual(len(queues), 3)
        self.assertEqual([queue["name"] for queue in queues], ["General reception", "Account services", "Priority support"])
        self.assertEqual(sum(queue["waiting"] for queue in queues), 13)
        self.assertEqual(second.get(f"/api/queues/{queues[0]['id']}").status_code, 404)
        self.assertGreater(first.get("/api/analytics").json()["completed"], 0)

    @override_settings(ENABLE_DEMO=False)
    def test_demo_can_be_disabled(self):
        self.assertEqual(self.post("/api/auth/demo", client=Client()).status_code, 404)

    def test_throttling_blocks_attempts_and_resets(self):
        for _ in range(40):
            services.throttle("test-ip", "auth")
        with self.assertRaises(services.APIError) as context:
            services.throttle("test-ip", "auth")
        self.assertEqual(context.exception.status, 429)
        RateLimit.objects.update(resets_at=0)
        services.throttle("test-ip", "auth")

    def test_database_enforces_number_and_service_uniqueness(self):
        queue = Queue.objects.create(manager=self.manager, name="Constraints", prefix="C")
        Token.objects.create(queue=queue, number=1, name="One", position=1, status="serving")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Token.objects.create(queue=queue, number=1, name="Duplicate", position=2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Token.objects.create(queue=queue, number=2, name="Second service", position=2, status="serving")


class ConcurrencyTests(TransactionTestCase):
    """Real connections and threads verify SQLite transaction boundaries."""
    def setUp(self):
        self.manager = Manager.objects.create_user("concurrent@example.com", name="Concurrency test")
        self.queue = services.create_queue(self.manager, {"name": "Concurrent arrivals"})

    def run_isolated(self, operation):
        close_old_connections()
        try:
            return operation()
        finally:
            connections.close_all()

    def test_concurrent_arrivals_never_reuse_numbers(self):
        def add(index):
            return self.run_isolated(lambda: services.add_token(self.manager, self.queue.id, {"name": f"Visitor {index}"}).number)
        with ThreadPoolExecutor(max_workers=4) as pool:
            numbers = list(pool.map(add, range(12)))
        self.assertEqual(sorted(numbers), list(range(1, 13)))

    def test_concurrent_call_next_only_assigns_one_token(self):
        services.add_token(self.manager, self.queue.id, {"name": "First"})
        services.add_token(self.manager, self.queue.id, {"name": "Second"})
        def call(_):
            def operation():
                try:
                    services.serve_next(self.manager, self.queue.id, {"revision": 2})
                    return 200
                except services.APIError as error:
                    return error.status
            return self.run_isolated(operation)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(call, range(2)))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(self.queue.tokens.filter(status="serving").count(), 1)
