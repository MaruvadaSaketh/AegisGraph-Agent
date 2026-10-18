"""AegisGraph-Agent: autonomous AML network investigation on FalkorDB.
Usage:
  python aegisgraph.py seed [--reset]           # load synthetic crime graph
  python aegisgraph.py investigate ACC-M01     # run agent + write SAR
"""
import os, sys, random, json, datetime as dt
from typing import Any
from dotenv import load_dotenv
from falkordb import FalkorDB
import networkx as nx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
GRAPH = os.getenv("FALKORDB_GRAPH", "aegisgraph")
THRESHOLD = 10_000  # reporting threshold (INR) for structuring logic


def detect_communities(
    account_ids: list[str], transfer_edges: list[tuple[str, str, float]]
) -> list[list[str]]:
    graph = nx.Graph()
    graph.add_nodes_from(account_ids)
    for source, target, weight in transfer_edges:
        if graph.has_edge(source, target):
            graph[source][target]["weight"] += weight
        else:
            graph.add_edge(source, target, weight=weight)

    if graph.number_of_edges() == 0:
        return []

    clusters = [
        sorted(members)
        for members in nx.community.louvain_communities(
            graph, weight="weight", seed=7
        )
        if len(members) > 1
    ]
    return sorted(clusters, key=lambda members: (-len(members), members))


def connect() -> tuple[FalkorDB, Any]:
    from app.database import get_graph

    return get_graph()


# ───────────────────────── SEED ─────────────────────────
def seed(reset: bool = False) -> None:
    db, g = connect()
    node_count = g.query("MATCH (n) RETURN count(n)").result_set[0][0]
    if node_count and not reset:
        raise RuntimeError(
            f"Graph '{GRAPH}' already contains {node_count} nodes. "
            "Use 'seed --reset' only if you intend to delete and replace its data."
        )
    if node_count and reset:
        g.delete()
    g = db.select_graph(GRAPH)
    random.seed(7)
    base = int(dt.datetime(2026, 9, 1).timestamp())
    day = 86400

    def node(label, id, **props):
        props["id"] = id
        g.query(f"MERGE (n:{label} {{id:$id}}) SET n += $p", {"id": id, "p": props})

    def rel(la, a, typ, lb, b, **p):
        g.query(f"MATCH (x:{la} {{id:$a}}),(y:{lb} {{id:$b}}) "
                f"CREATE (x)-[r:{typ}]->(y) SET r += $p",
                {"a": a, "b": b, "p": p})

    for c, n, hr in [("IN", "India", False), ("AE", "UAE", False), ("KY", "Cayman Islands", True), ("PA", "Panama", True)]:
        node("Country", c, name=n, high_risk=hr)
    node("Watchlist", "WL-1", name="FATF Grey-List Linked Entities")
    g.query("CREATE INDEX FOR (n:Customer) ON (n.id)")
    g.query("CREATE INDEX FOR (n:Account) ON (n.id)")

    tid = [0]
    def transfer(a, b, amt, t):
        tid[0] += 1
        rel("Account", a, "TRANSFER", "Account", b, amount=amt, ts=t, tid=f"TX-{tid[0]:04d}")

    def customer(cid, name, acc, phone=None, device=None, addr=None, ip=None, tax=None):
        node("Customer", cid, name=name)
        node("Account", acc, opened=base - 400 * day)
        rel("Customer", cid, "OWNS", "Account", acc)
        for lbl, rt, val, pfx in [("Phone", "HAS_PHONE", phone, "PH"), ("Device", "USES_DEVICE", device, "DV"),
                                  ("Address", "LIVES_AT", addr, "AD"), ("IP", "USES_IP", ip, "IP"),
                                  ("TaxID", "HAS_TAXID", tax, "TX")]:
            val = val or f"{pfx}-{cid}"
            node(lbl, val)
            rel("Customer", cid, rt, lbl, val)

    # background population
    normal = []
    for i in range(1, 61):
        customer(f"CUS-N{i:03d}", f"Normal {i}", f"ACC-N{i:03d}")
        normal.append(f"ACC-N{i:03d}")
    node("Merchant", "MER-GROC", name="City Grocers", category="retail"); rel("Merchant", "MER-GROC", "LOCATED_IN", "Country", "IN")
    for _ in range(160):
        a, b = random.sample(normal, 2)
        transfer(a, b, random.randint(500, 60000), base + random.randint(0, 28 * day))
    for a in normal[:30]:
        rel("Account", a, "PAID", "Merchant", "MER-GROC", amount=random.randint(200, 4000), ts=base + random.randint(0, 28 * day))

    # synthetic identity ring: R1-R2 phone, R2-R3 device, R3-R4 address, R4-R1 IP
    customer("CUS-R1", "Ring One", "ACC-R1", phone="PH-SHARED", ip="IP-SHARED")
    customer("CUS-R2", "Ring Two", "ACC-R2", phone="PH-SHARED", device="DV-SHARED")
    customer("CUS-R3", "Ring Three", "ACC-R3", device="DV-SHARED", addr="AD-SHARED")
    customer("CUS-R4", "Ring Four", "ACC-R4", addr="AD-SHARED", ip="IP-SHARED")

    # offshore sink
    node("Merchant", "MER-OFF", name="Blue Harbor Trading Ltd", category="consulting")
    rel("Merchant", "MER-OFF", "LOCATED_IN", "Country", "KY")
    rel("Merchant", "MER-OFF", "LISTED_ON", "Watchlist", "WL-1")

    # smurfing: 12 mules -> 3 intermediaries (R1-R3) -> aggregator (R4) -> offshore
    inter = ["ACC-R1", "ACC-R2", "ACC-R3"]
    for i in range(1, 13):
        customer(f"CUS-M{i:02d}", f"Mule {i}", f"ACC-M{i:02d}")
        for k in range(2):
            transfer(f"ACC-M{i:02d}", inter[(i + k) % 3], random.randint(7800, 9700), base + (10 + i // 3 + k) * day)
    for k, a in enumerate(inter):
        transfer(a, "ACC-R4", random.randint(60000, 75000), base + (16 + k) * day)
    for k in range(3):
        rel("Account", "ACC-R4", "PAID", "Merchant", "MER-OFF", amount=random.randint(190000, 215000), ts=base + (19 + k) * day)
    print(f"Seeded graph '{GRAPH}': {g.query('MATCH (n) RETURN count(n)').result_set[0][0]} nodes, "
          f"{g.query('MATCH ()-[r]->() RETURN count(r)').result_set[0][0]} edges. Alert account to try: ACC-M01")


# ───────────────────────── AGENT ─────────────────────────
class Agent:
    def __init__(self, acc: str) -> None:
        self.db, self.g = connect()
        self.acc = acc
        self.trail: list[str] = []
        self.log: list[tuple[str, dict[str, Any]]] = []

    def close(self) -> None:
        close = getattr(self.db, "close", None)
        if callable(close):
            close()

    def q(self, cy: str, **p: Any) -> list[list[Any]]:
        self.log.append((cy.strip(), p))
        return self.g.query(cy, p).result_set

    def think(self, msg: str) -> None:
        print("🧠", msg); self.trail.append(msg)

    def run(self) -> dict[str, Any]:
        a = self.acc
        # 1. identify entity
        r = self.q("MATCH (c:Customer)-[:OWNS]->(a:Account {id:$a}) RETURN c.id, c.name", a=a)
        if not r:
            raise LookupError(f"Account {a} not found")
        cust = r[0][0]
        self.think(f"Alert on {a} owned by {cust} ({r[0][1]}). Expanding network.")

        # 2. network membership (WCC server-side, networkx fallback)
        comp = self.component(a)
        accs = sorted(x for x in comp if x.startswith("ACC-"))
        custs = sorted(x for x in comp if x.startswith("CUS-"))
        self.think(f"Weakly connected component: {len(comp)} entities ({len(custs)} customers, {len(accs)} accounts).")

        # 3. structuring / fan-in
        fan = [x for x in self.q(
            """MATCH (s:Account)-[t:TRANSFER]->(x:Account)
               WHERE t.amount >= $lo AND t.amount < $thr
               WITH x, count(DISTINCT s) AS senders, sum(t.amount) AS total, count(t) AS n
               WHERE senders >= 3 RETURN x.id, senders, n, total ORDER BY senders DESC""",
            lo=int(THRESHOLD * 0.75), thr=THRESHOLD) if x[0] in comp]
        self.think(f"Sub-threshold fan-in (smurfing) at: {[f[0] for f in fan] or 'none'}")

        # 4. money flow to high-risk jurisdiction
        paths = self.q(
            """MATCH p=(a:Account {id:$a})-[:TRANSFER*1..5]->(:Account)-[:PAID]->(m:Merchant)-[:LOCATED_IN]->(c:Country {high_risk:true})
               RETURN [n IN nodes(p) | n.id] AS ids, m.id, m.name, c.name,
                      [r IN relationships(p) | r.amount] AS amts LIMIT 10""", a=a)
        self.think(f"{len(paths)} money-flow path(s) from {a} to a high-risk jurisdiction.")

        # 5. shared identity resources inside the network
        shared = self.q(
            """MATCH (c1:Customer)-[r1]->(res)<-[r2]-(c2:Customer)
               WHERE c1.id < c2.id AND c1.id IN $m AND c2.id IN $m
                 AND type(r1) IN ['HAS_PHONE','USES_DEVICE','LIVES_AT','USES_IP','HAS_TAXID']
               RETURN c1.id, type(r1), res.id, c2.id""", m=custs)
        self.think(f"{len(shared)} shared-identity links between customers in the network.")

        # 6. betweenness on money-flow graph
        broker = self.betweenness(accs)
        self.think(f"Top intermediaries by betweenness: {broker[:3]}")

        # 7. community detection on the account transfer network
        transfer_edges = self.q(
            """MATCH (s:Account)-[t:TRANSFER]->(x:Account)
               WHERE s.id IN $ids AND x.id IN $ids
               RETURN s.id, x.id, count(t)""",
            ids=accs,
        )
        communities = detect_communities(accs, transfer_edges)
        self.think(f"Transfer communities identified: {communities[:5] or 'none'}")

        # 8. watchlist / sanctions
        wl = self.q("MATCH (m:Merchant)-[:LISTED_ON]->(w:Watchlist) RETURN m.id, m.name, w.name")
        wl = [w for w in wl if any(p[1] == w[0] for p in paths)]

        # 9. score
        score, why = 0, []
        if fan: score += 25; why.append("Structuring: many sub-threshold senders aggregating into one account (+25)")
        if len({s[0] for s in shared} | {s[3] for s in shared}) >= 3: score += 25; why.append("Synthetic-identity cluster: ≥3 customers sharing identity resources (+25)")
        if paths: score += 20; why.append("Funds reach a high-risk jurisdiction (+20)")
        if wl: score += 20; why.append("Destination merchant is on a watchlist (+20)")
        if broker and broker[0][1] > 0: score += 10; why.append("Critical intermediary accounts identified (+10)")
        self.think(f"Network risk score: {score}/100")
        return dict(acc=a, cust=cust, comp=comp, custs=custs, accs=accs, fan=fan, paths=paths,
                    shared=shared, broker=broker, communities=communities, wl=wl,
                    score=score, why=why)

    def component(self, acc: str) -> set[str]:
        labels = ["Customer", "Account", "Device", "Phone", "Address", "IP", "TaxID", "Merchant"]
        rels = ["OWNS", "TRANSFER", "PAID", "HAS_PHONE", "USES_DEVICE", "LIVES_AT", "USES_IP", "HAS_TAXID"]
        try:
            rows = self.q("CALL algo.WCC({nodeLabels:$l, relationshipTypes:$r}) YIELD node, componentId RETURN node.id, componentId", l=labels, r=rels)
            cid = next(c for n, c in rows if n == acc)
            return {n for n, c in rows if c == cid}
        except Exception:
            G = nx.Graph()
            G.add_edges_from((a, b) for a, b in self.q("MATCH (a)-[r]->(b) WHERE type(r) <> 'LOCATED_IN' AND type(r) <> 'LISTED_ON' RETURN a.id, b.id"))
            return nx.node_connected_component(G, acc)

    def betweenness(self, accs: list[str]) -> list[tuple[str, float]]:
        try:
            rows = self.q("CALL algo.betweenness({nodeLabels:['Account'], relationshipTypes:['TRANSFER']}) YIELD node, score RETURN node.id, score")
            rows = [(n, s) for n, s in rows if n in accs]
        except Exception:
            D = nx.DiGraph(); D.add_edges_from(self.q("MATCH (a:Account)-[:TRANSFER]->(b:Account) RETURN a.id, b.id"))
            bc = nx.betweenness_centrality(D)
            rows = [(n, bc.get(n, 0)) for n in accs]
        return sorted([(n, round(s, 4)) for n, s in rows], key=lambda x: -x[1])


# ───────────────────────── SAR ─────────────────────────
def sar(f: dict[str, Any], agent: Agent, include_llm_narrative: bool = True) -> str:
    indicators = f["why"] or ["No configured risk indicators were found."]
    L = [f"# Suspicious Activity Report (DRAFT) – {f['acc']}",
         f"_Generated {dt.datetime.now():%Y-%m-%d %H:%M} by AegisGraph-Agent_\n",
         f"## Risk Score: {f['score']}/100", *[f"- {w}" for w in indicators],
         "\n## Summary",
         f"Alert on **{f['acc']}** ({f['cust']}) belongs to a connected network of "
         f"**{len(f['custs'])} customers** and **{len(f['accs'])} accounts**. "
         f"Investigation findings: {'; '.join(f['why']) if f['why'] else 'no configured risk indicators identified'}."]
    if f["fan"]:
        L += ["\n## Structuring / Aggregation", *[f"- `{a}` received {n} sub-threshold transfers from {s} senders, total ₹{t:,.0f}" for a, s, n, t in f["fan"]]]
    if f["shared"]:
        L += ["\n## Shared Identity Evidence", *[f"- {a} ⇄ {b} via {t} `{r}`" for a, t, r, b in f["shared"]]]
    if f["paths"]:
        L += ["\n## Money-Flow Paths"]
        for ids, mid, mname, ctry, amts in f["paths"]:
            L.append(f"- {' → '.join(ids)} → {mname} ({ctry}); hop amounts: {amts}")
    if f["broker"]:
        L += ["\n## Critical Intermediaries (betweenness)", *[f"- {n}: {s}" for n, s in f["broker"][:5]]]
    if f["communities"]:
        L += ["\n## Transfer Communities",
              *[f"- Community {i}: {', '.join(members)}"
                for i, members in enumerate(f["communities"], start=1)]]
    if f["wl"]:
        L += ["\n## Watchlist", *[f"- {n} ({i}) listed on {w}" for i, n, w in f["wl"]]]
    L += ["\n## Agent Reasoning Trail", *[f"{i+1}. {t}" for i, t in enumerate(agent.trail)],
          "\n## Cypher Evidence", *[f"```cypher\n{c}\n```\nparams: `{json.dumps(p, default=str)[:300]}`" for c, p in agent.log]]
    text = "\n".join(L)
    if include_llm_narrative and os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            m = anthropic.Anthropic().messages.create(
                model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"), max_tokens=700,
                messages=[{"role": "user", "content": "Write a concise, factual SAR narrative (no speculation) from these findings:\n" + "\n".join(L[:30])}])
            text = text.replace("## Summary", "## Narrative\n" + m.content[0].text + "\n\n## Summary", 1)
        except Exception as e:
            print("LLM narrative skipped:", e)
    return text


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "seed":
        seed(reset="--reset" in sys.argv[2:])
    elif cmd == "investigate":
        ag = Agent(sys.argv[2] if len(sys.argv) > 2 else "ACC-M01")
        res = ag.run()
        out = f"SAR_{res['acc']}.md"
        with open(out, "w", encoding="utf-8") as report:
            report.write(sar(res, ag))
        print(f"\n📄 SAR written to {out}")
    else:
        print(__doc__)
