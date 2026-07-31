import unittest


class VercelServerlessTests(unittest.TestCase):
    def test_entry_point_exports_fastapi_app(self):
        from api import index

        self.assertEqual(index.app.__class__.__name__, "FastAPI")

    def test_entry_point_uses_temporary_sqlite_database(self):
        from api import index

        self.assertEqual(index.DATABASE_URL, "sqlite:////tmp/xfidear-demo.db")
