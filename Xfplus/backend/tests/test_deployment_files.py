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

    def test_root_vercel_config_builds_frontend_and_routes_api_first(self):
        config = json.loads((REPOSITORY_ROOT / "vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(config["outputDirectory"], "Xfplus/frontend/dist")
        self.assertEqual(config["rewrites"][0], {"source": "/api/(.*)", "destination": "/api/index.py"})
        self.assertEqual(config["rewrites"][1], {"source": "/(.*)", "destination": "/index.html"})

    def test_vercel_only_guide_documents_data_reset_and_same_origin_api(self):
        guide = (ROOT / "docs" / "DEPLOY_VERCEL_SERVERLESS.md").read_text(encoding="utf-8")
        self.assertIn("/tmp", guide)
        self.assertIn("VITE_API_BASE_URL", guide)
        self.assertIn("city_demo / 123456", guide)
