import os
from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

def get_graph():
    """Connect to the existing graph without resetting or deleting data."""
    config = {
        "host": os.getenv("FALKORDB_HOST", "127.0.0.1"),
        "port": int(os.getenv("FALKORDB_PORT", "6379")),
    }
    username = os.getenv("FALKORDB_USERNAME", "").strip()
    password = os.getenv("FALKORDB_PASSWORD", "")
    if username:
        config["username"] = username
    if password:
        config["password"] = password
    if os.getenv("FALKORDB_SSL", "false").lower() == "true":
        config["ssl"] = True

    client = FalkorDB(**config)
    graph = client.select_graph(os.getenv("FALKORDB_GRAPH", "aegisgraph"))
    return client, graph
