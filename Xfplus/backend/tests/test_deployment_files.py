import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = ROOT.parent


class DeploymentFilesTests(unittest.TestCase):
    def test_vercel_rewrites_all_routes_to_index(self):
        config = json.loads((ROOT / "frontend" / "vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(config["rewrites"], [{"source": "/(.*)", "destination": "/index.html"}])

    def test_render_service_uses_fastapi_health_check(self):
        content = (REPOSITORY_ROOT / "render.yaml").read_text(encoding="utf-8")
        self.assertIn("healthCheckPath: /api/health", content)
        self.assertIn("uvicorn backend.main:app --host 0.0.0.0 --port $PORT", content)

    def test_deployment_guide_documents_required_variables_and_smoke_tests(self):
        guide = (ROOT / "docs" / "DEPLOY_VERCEL_RENDER.md").read_text(encoding="utf-8")
        for expected in (
            "VITE_API_BASE_URL",
            "FRONTEND_ORIGIN",
            "/api/health",
            "city_demo / 123456",
            "SQLite",
        ):
            self.assertIn(expected, guide)
