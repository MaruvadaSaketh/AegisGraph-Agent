"""Controlled graph operations used by the HTTP API."""

import argparse
import json
from typing import Any

from aegisgraph import Agent, sar


def _account_agent(account_id: str) -> tuple[Agent, list[Any], set[str]]:
    agent = Agent(account_id)
    try:
        owner = agent.q(
            "MATCH (c:Customer)-[:OWNS]->(a:Account {id:$account_id}) "
            "RETURN c.id, c.name",
            account_id=account_id,
        )
        if not owner:
            raise LookupError(f"Account {account_id} not found")
        component = agent.component(account_id)
        return agent, owner[0], component
    except Exception:
        agent.close()
        raise


def get_account_context(account_id: str) -> dict[str, Any]:
    """Return account ownership and connected-network context."""
    agent, owner, component = _account_agent(account_id)
    try:
        return {
            "account_id": account_id,
            "customer_id": owner[0],
            "customer_name": owner[1],
            "network": {
                "entity_count": len(component),
                "customer_ids": sorted(
                    entity for entity in component if entity.startswith("CUS-")
                ),
                "account_ids": sorted(
                    entity for entity in component if entity.startswith("ACC-")
                ),
            },
        }
    finally:
        agent.close()


def trace_fund_flows(account_id: str) -> dict[str, Any]:
    """Trace account transfers that reach a high-risk jurisdiction."""
    agent, _, _ = _account_agent(account_id)
    try:
        rows = agent.q(
            """MATCH p=(a:Account {id:$account_id})-[:TRANSFER*1..5]->(:Account)
                   -[:PAID]->(m:Merchant)-[:LOCATED_IN]->
                   (c:Country {high_risk:true})
               RETURN [n IN nodes(p) | n.id] AS ids, m.id, m.name, c.name,
                      [r IN relationships(p) | r.amount] AS amounts
               LIMIT 10""",
            account_id=account_id,
        )
        return {
            "account_id": account_id,
            "paths": [
                {
                    "entity_path": row[0],
                    "merchant_id": row[1],
                    "merchant_name": row[2],
                    "country": row[3],
                    "amounts": row[4],
                }
                for row in rows
            ],
            "evidence": agent.log,
        }
    finally:
        agent.close()


def investigate_account(account_id: str) -> dict[str, Any]:
    """Investigate an account and return findings with auditable evidence."""
    agent = Agent(account_id)
    try:
        result = agent.run()

        paths = [
            {
                "account_path": row[0],
                "merchant_id": row[1],
                "merchant_name": row[2],
                "country": row[3],
                "amounts": row[4],
            }
            for row in result["paths"]
        ]
        shared_identity_links = [
            {
                "customer_a": row[0],
                "relationship": row[1],
                "resource_id": row[2],
                "customer_b": row[3],
            }
            for row in result["shared"]
        ]

        return {
            "account_id": result["acc"],
            "customer_id": result["cust"],
            "risk_score": result["score"],
            "risk_factors": result["why"],
            "network": {
                "entity_count": len(result["comp"]),
                "customer_count": len(result["custs"]),
                "account_count": len(result["accs"]),
            },
            "structuring_indicators": [
                {
                    "account_id": row[0],
                    "distinct_senders": row[1],
                    "transfer_count": row[2],
                    "total_amount": row[3],
                }
                for row in result["fan"]
            ],
            "money_flow_paths": paths,
            "shared_identity_links": shared_identity_links,
            "critical_intermediaries": [
                {"account_id": account_id, "betweenness": score}
                for account_id, score in result["broker"][:5]
            ],
            "communities": result["communities"],
            "watchlist_matches": [
                {"merchant_id": row[0], "merchant_name": row[1], "watchlist": row[2]}
                for row in result["wl"]
            ],
            "evidence": [
                {"query": query, "parameters": parameters}
                for query, parameters in agent.log
            ],
            "reasoning_trail": agent.trail,
            "sar_draft": sar(result, agent, include_llm_narrative=False),
        }
    finally:
        agent.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Investigate an account in FalkorDB.")
    parser.add_argument("account_id", nargs="?", default="ACC-M01")
    args = parser.parse_args()
    result = investigate_account(args.account_id)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
