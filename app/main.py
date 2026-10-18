import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from app.database import get_graph

GRAPH_NAME = os.getenv("FALKORDB_GRAPH", "aegisgraph")
UI_PATH = Path(__file__).parent / "static" / "index.html"

app = FastAPI(title="AegisGraph-Agent API", version="0.2.0")
ACCOUNT_ID_PATTERN = re.compile(r"ACC-[A-Za-z0-9_-]{1,60}")


def _close_client(client):
    close = getattr(client, "close", None)
    if callable(close):
        close()


@app.get("/")
def root() -> FileResponse:
    return FileResponse(UI_PATH)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(
        content=(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            '<rect width="64" height="64" rx="16" fill="#0b1720"/>'
            '<path d="M17 32 32 16l15 16-15 16z" fill="none" '
            'stroke="#4ee0bd" stroke-width="5"/>'
            '<circle cx="17" cy="32" r="4" fill="#4ee0bd"/>'
            '<circle cx="32" cy="16" r="4" fill="#4ee0bd"/>'
            '<circle cx="47" cy="32" r="4" fill="#4ee0bd"/>'
            '<circle cx="32" cy="48" r="4" fill="#4ee0bd"/>'
            "</svg>"
        ),
        media_type="image/svg+xml",
    )


@app.get("/health")
def health() -> dict[str, bool | str]:
    client = None
    try:
        client, graph = get_graph()
        result = graph.query("RETURN 1 AS connected")
        ok = bool(result.result_set and result.result_set[0][0] == 1)
        if not ok:
            raise HTTPException(status_code=503, detail="FalkorDB health query failed.")
        return {"status": "ok", "falkordb_connected": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="FalkorDB connection failed; check .env host, port, graph, credentials, and TLS.",
        ) from exc
    finally:
        if client is not None:
            _close_client(client)


@app.get("/schema")
def schema() -> dict[str, str | list[str]]:
    client = None
    try:
        client, graph = get_graph()
        labels = graph.query("CALL db.labels()")
        rels = graph.query("CALL db.relationshipTypes()")
        return {
            "graph": GRAPH_NAME,
            "labels": [r[0] for r in labels.result_set],
            "relationship_types": [r[0] for r in rels.result_set],
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not read graph schema.") from exc
    finally:
        if client is not None:
            _close_client(client)


@app.get("/graph/summary")
def graph_summary() -> dict[str, object]:
    """Return counts and schema metadata for the configured graph."""
    client = None
    try:
        client, graph = get_graph()
        node_count = graph.query("MATCH (n) RETURN count(n)").result_set[0][0]
        relationship_count = graph.query(
            "MATCH ()-[r]->() RETURN count(r)"
        ).result_set[0][0]

        labels = graph.query("CALL db.labels()").result_set
        relationship_types = graph.query("CALL db.relationshipTypes()").result_set
        return {
            "graph": GRAPH_NAME,
            "node_count": node_count,
            "relationship_count": relationship_count,
            "labels": [row[0] for row in labels],
            "relationship_types": [row[0] for row in relationship_types],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not read graph summary; verify FalkorDB is available.",
        ) from exc
    finally:
        if client is not None:
            _close_client(client)


@app.get("/investigate/transfers")
def investigate_transfers(max_hops: int = 4, limit: int = 20) -> dict[str, object]:
    if not 1 <= max_hops <= 5:
        raise HTTPException(status_code=400, detail="max_hops must be between 1 and 5")
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    client = None
    try:
        client, graph = get_graph()
        query = f"""
        MATCH p = (a:Account)-[:TRANSFER*1..{max_hops}]->(b:Account)
        RETURN [n IN nodes(p) | {{
          labels: labels(n),
          id: coalesce(n.id, n.account_id, n.name)
        }}] AS path, length(p) AS hops
        LIMIT {limit}
        """
        result = graph.query(query)
        return {"graph": GRAPH_NAME, "count": len(result.result_set),
                "results": [{"path": row[0], "hops": row[1]} for row in result.result_set]}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Transfer query failed; confirm Account nodes and TRANSFER relationships.") from exc
    finally:
        if client is not None:
            _close_client(client)


@app.get("/investigate/shared-devices")
def investigate_shared_devices(limit: int = 50) -> dict[str, object]:
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    client = None
    try:
        client, graph = get_graph()
        query = f"""
        MATCH (c1:Customer)-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(c2:Customer)
        WHERE c1 <> c2
          AND coalesce(c1.id, c1.name, '') < coalesce(c2.id, c2.name, '')
        RETURN coalesce(c1.id, c1.name) AS customer_1,
               coalesce(c2.id, c2.name) AS customer_2,
               coalesce(d.id, d.device_id, d.name) AS shared_device
        LIMIT {limit}
        """
        result = graph.query(query)
        return {"graph": GRAPH_NAME, "count": len(result.result_set),
                "results": [{"customer_1": r[0], "customer_2": r[1], "shared_device": r[2]}
                            for r in result.result_set]}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Shared-device query failed; confirm Customer/Device labels and USES_DEVICE relationships.") from exc
    finally:
        if client is not None:
            _close_client(client)


@app.get("/accounts")
def list_accounts() -> dict[str, list[str]]:
    """Return account IDs that are linked to a customer and can be investigated."""
    client = None
    try:
        client, graph = get_graph()
        result = graph.query(
            """
            MATCH (:Customer)-[:OWNS]->(a:Account)
            WHERE a.id IS NOT NULL
            RETURN DISTINCT a.id
            ORDER BY a.id
            """
        )
        return {"accounts": [row[0] for row in result.result_set]}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not load accounts; verify FalkorDB is available.",
        ) from exc
    finally:
        if client is not None:
            _close_client(client)


@app.get("/investigate/{account_id}")
def investigate_account(account_id: str) -> dict[str, object]:
    if not ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise HTTPException(
            status_code=422,
            detail="account_id must be a valid ACC- identifier.",
        )
    try:
        from app.graph_service import investigate_account as run_investigation

        return run_investigation(account_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Account investigation failed; verify the graph and its schema.",
        ) from exc
