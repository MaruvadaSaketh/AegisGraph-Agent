import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from aegisgraph import detect_communities, sar


class CommunityDetectionTests(unittest.TestCase):
    def test_returns_disconnected_transfer_groups_and_omits_isolates(self):
        communities = detect_communities(
            ["ACC-A", "ACC-B", "ACC-C", "ACC-D", "ACC-ISOLATED"],
            [
                ("ACC-A", "ACC-B", 2),
                ("ACC-C", "ACC-D", 1),
            ],
        )

        self.assertEqual(communities, [["ACC-A", "ACC-B"], ["ACC-C", "ACC-D"]])

    def test_returns_no_communities_without_transfer_edges(self):
        self.assertEqual(detect_communities(["ACC-A", "ACC-B"], []), [])


class ReportTests(unittest.TestCase):
    def test_summary_does_not_claim_unobserved_laundering(self):
        findings = {
            "acc": "ACC-A",
            "cust": "CUS-A",
            "custs": ["CUS-A"],
            "accs": ["ACC-A"],
            "fan": [],
            "paths": [],
            "shared": [],
            "broker": [],
            "communities": [],
            "wl": [],
            "score": 0,
            "why": [],
        }
        agent = SimpleNamespace(trail=[], log=[])

        with patch.dict(os.environ, {}, clear=True):
            report = sar(findings, agent)

        self.assertIn("no configured risk indicators identified", report)
        self.assertNotIn("moved to an offshore destination", report)

    def test_report_includes_transfer_communities(self):
        findings = {
            "acc": "ACC-A",
            "cust": "CUS-A",
            "custs": ["CUS-A"],
            "accs": ["ACC-A", "ACC-B"],
            "fan": [],
            "paths": [],
            "shared": [],
            "broker": [],
            "communities": [["ACC-A", "ACC-B"]],
            "wl": [],
            "score": 0,
            "why": [],
        }
        agent = SimpleNamespace(trail=[], log=[])

        with patch.dict(os.environ, {}, clear=True):
            report = sar(findings, agent)

        self.assertIn("## Transfer Communities", report)
        self.assertIn("Community 1: ACC-A, ACC-B", report)


if __name__ == "__main__":
    unittest.main()
