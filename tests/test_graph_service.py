import unittest
from unittest.mock import patch

from app.graph_service import investigate_account
from aegisgraph import connect


class GraphServiceTests(unittest.TestCase):
    @patch("app.database.get_graph")
    def test_investigation_connection_uses_shared_database_settings(self, get_graph):
        connection = (object(), object())
        get_graph.return_value = connection

        self.assertIs(connect(), connection)

    @patch("app.graph_service.Agent")
    def test_investigation_closes_database_client_after_failure(self, agent_class):
        agent = agent_class.return_value
        agent.run.side_effect = RuntimeError("query failed")

        with self.assertRaisesRegex(RuntimeError, "query failed"):
            investigate_account("ACC-1")

        agent.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
