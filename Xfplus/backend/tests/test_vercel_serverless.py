import unittest

from fastapi.testclient import TestClient


class VercelServerlessTests(unittest.TestCase):
    def test_entry_point_exports_fastapi_app(self):
        from api import index

        self.assertEqual(index.app.__class__.__name__, "FastAPI")

    def test_entry_point_uses_temporary_sqlite_database(self):
        from api import index

        self.assertIn("xfidear-demo.db", index.DATABASE_URL)

    def test_seeded_city_demo_account_can_log_in(self):
        from api import index

        client = TestClient(index.app)
        response = client.post(
            "/api/auth/login",
            json={"username": "city_demo", "password": "123456"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["username"], "city_demo")
