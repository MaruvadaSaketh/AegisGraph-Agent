# AegisGraph-Agent Demo Video Script

**Target length:** 2–3 minutes  
**Hackathon track:** Agents That Act on Connected Data  
**Demo account:** `ACC-M01` from the synthetic seed graph  
**Audience:** Graph Hacks judges and developers evaluating graph-native agents

## Before recording

1. Start FalkorDB and confirm the host, port, graph name, and any credentials in `.env`.
2. From the project root, seed a clean demo graph if needed:

   ```powershell
   python aegisgraph.py seed
   ```

   The seed command refuses to overwrite a non-empty graph. Use `python aegisgraph.py seed --reset` only when it is safe to replace the contents of the configured demo graph.

3. Start the app:

   ```powershell
   uvicorn app.main:app --reload
   ```

4. Confirm `http://127.0.0.1:8000/health` reports a successful FalkorDB connection. Open the dashboard at `http://127.0.0.1:8000/`.
5. Use only the generated synthetic demo data. Keep credentials and `.env` off-screen. Select `ACC-M01` for the walkthrough.

If a seeded investigation does not show the expected signals, verify the seed completed and that the app is connected to the same graph named in `.env` before recording. Do not narrate placeholder or unavailable results as live findings.

## Timed walkthrough

### 0:00–0:18 — Hook: the context gap

**Show:** Title card, then the dashboard.

**Say:**

> “A suspicious payment rarely explains itself. The important clues may be spread across accounts, transfers, shared identities, merchants, and jurisdictions. AegisGraph-Agent puts those connections in the investigation itself—not just in a visualization.”

### 0:18–0:40 — Establish that this is a live graph-backed app

**Show:** The dashboard connection status and graph overview metrics. Briefly point to the connected graph name and node and relationship counts.

**Say:**

> “This dashboard is connected to FalkorDB, which is the primary graph database behind the product. The graph links customers and accounts to transfers, merchants, countries, watchlists, and shared identity resources. Those relationships are the evidence the investigation follows.”

### 0:40–1:03 — Choose the synthetic alert

**Show:** Select `ACC-M01` in the account picker and start the investigation.

**Say:**

> “For this demo I’m using `ACC-M01`, an account in our synthetic dataset. The system first resolves who owns it, then expands the connected network. It does not treat an isolated transaction as the whole story.”

### 1:03–1:38 — Reveal the connected pattern

**Show:** The network map and investigation signals. Point to transfer paths, shared identity evidence, and the risk factors actually returned by the running app.

**Say:**

> “Here, the graph lets us examine several kinds of evidence together: sub-threshold transfer fan-in, shared identity links, and routes from accounts to merchants in high-risk jurisdictions. The map helps an analyst see how these entities connect; the signal panel makes the reasons inspectable.”

**Recording note:** Name only signals visible in the completed investigation. Do not state a score, amount, count, customer identity, or destination unless it is shown in this run.

### 1:38–2:05 — Show why graph traversal matters

**Show:** The destination flow paths and shared identity signals, then briefly open `/docs` or the README’s query section.

**Say:**

> “This is graph reasoning in the product’s core workflow. Cypher traverses transfer paths and shared relationships in FalkorDB. Graph analysis identifies connected components and intermediary accounts, while community detection highlights groups in the transfer network. The result is evidence with query context—not a black-box label.”

### 2:05–2:27 — Responsible conclusion and close

**Show:** Return to the findings/dashboard and the human-review reminder.

**Say:**

> “AegisGraph-Agent helps investigators decide where to look next; it does not decide that a person committed a crime. The data in this demo is synthetic, and every finding requires qualified human review. AegisGraph-Agent: connected context for decisions you can trace.”

**End card:** `AegisGraph-Agent` · FalkorDB · Agents That Act on Connected Data  
Add the public repository URL and demo video URL to the hackathon submission.

## Editing and judging checklist

- Keep the FalkorDB connected state and live investigation results visible long enough to read.
- Show the actual account selection, network map, risk factors, and at least one evidence panel.
- Keep `.env`, passwords, API keys, and unrelated personal data out of frame.
- Avoid presenting risk scores or graph links as proof of wrongdoing.
- Confirm the submission names the track and includes the public source repository and README.
- Paste the final video URL into [SUBMISSION.md](./SUBMISSION.md) before submitting.
