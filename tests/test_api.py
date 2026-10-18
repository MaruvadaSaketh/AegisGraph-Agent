import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.main import app


class ApiEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db_client = Mock()
        self.graph = Mock()
        self.db_client.close = Mock()

    def test_root_serves_dashboard(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Investigation overview", response.text)
        self.assertIn("Network map", response.text)

    def test_favicon_is_available(self):
        response = self.client.get("/favicon.ico")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/svg+xml")

    @patch("app.main.get_graph")
    def test_health_checks_falkordb(self, get_graph):
        self.graph.query.return_value = SimpleNamespace(result_set=[[1]])
        get_graph.return_value = (self.db_client, self.graph)

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "falkordb_connected": True},
        )
        self.db_client.close.assert_called_once_with()

    @patch("app.main.get_graph")
    def test_schema_returns_labels_and_relationship_types(self, get_graph):
        self.graph.query.side_effect = [
            SimpleNamespace(result_set=[["Account"], ["Customer"]]),
            SimpleNamespace(result_set=[["OWNS"], ["TRANSFER"]]),
        ]
        get_graph.return_value = (self.db_client, self.graph)

        response = self.client.get("/schema")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["labels"], ["Account", "Customer"])
        self.assertEqual(
            response.json()["relationship_types"], ["OWNS", "TRANSFER"]
        )

    @patch("app.main.get_graph")
    def test_graph_summary_returns_counts_and_schema(self, get_graph):
        self.graph.query.side_effect = [
            SimpleNamespace(result_set=[[537]]),
            SimpleNamespace(result_set=[[679]]),
            SimpleNamespace(result_set=[["Account"], ["Customer"]]),
            SimpleNamespace(result_set=[["OWNS"], ["TRANSFER"]]),
        ]
        get_graph.return_value = (self.db_client, self.graph)

        response = self.client.get("/graph/summary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "graph": "aegisgraph",
                "node_count": 537,
                "relationship_count": 679,
                "labels": ["Account", "Customer"],
                "relationship_types": ["OWNS", "TRANSFER"],
            },
        )
        self.db_client.close.assert_called_once_with()

    @patch("app.main.get_graph", side_effect=ConnectionError("private details"))
    def test_graph_summary_hides_internal_database_errors(self, _get_graph):
        response = self.client.get("/graph/summary")

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private details", response.text)

    @patch("app.graph_service.investigate_account", return_value={"risk_score": 90})
    def test_account_investigation_route_returns_findings(self, run_investigation):
        response = self.client.get("/investigate/ACC-M01")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"risk_score": 90})
        run_investigation.assert_called_once_with("ACC-M01")

    def test_account_investigation_validates_account_id(self):
        response = self.client.get("/investigate/not-an-account")

        self.assertEqual(response.status_code, 422)

    def test_account_investigation_rejects_invalid_account_id_characters(self):
        response = self.client.get("/investigate/ACC-..")

        self.assertEqual(response.status_code, 422)

    @patch("app.main.get_graph")
    def test_accounts_returns_sorted_investigable_ids(self, get_graph):
        self.graph.query.return_value = SimpleNamespace(
            result_set=[["ACC-N011"], ["ACC-N012"]]
        )
        get_graph.return_value = (self.db_client, self.graph)

        response = self.client.get("/accounts")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"accounts": ["ACC-N011", "ACC-N012"]},
        )
        self.graph.query.assert_called_once()
        self.db_client.close.assert_called_once_with()

    @patch("app.main.get_graph", side_effect=ConnectionError("private details"))
    def test_accounts_hides_internal_database_errors(self, _get_graph):
        response = self.client.get("/accounts")

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private details", response.text)


if __name__ == "__main__":
    unittest.main()
