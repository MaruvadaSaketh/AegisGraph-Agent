# Graph Hacks Submission

## Project

**AegisGraph-Agent** is a FalkorDB-powered AML investigation assistant that traverses connected transaction and identity data to surface explainable risk indicators for human review.

## Track

Agents That Act on Connected Data

## What it does

The application investigates a selected account by expanding its connected network and looking for:

- Sub-threshold transfer fan-in patterns
- Transfers that reach merchants in high-risk jurisdictions
- Customers connected through shared identity resources
- Central intermediary accounts and transfer communities
- Merchants linked to watchlists

It returns evidence-backed findings, the Cypher queries used, and a draft suspicious activity report. Findings are investigation leads, not proof of criminal conduct; qualified human review is required.

## Technology and graph model

FalkorDB is the primary graph database. The graph connects `Customer`, `Account`, `Merchant`, `Country`, `Watchlist`, `Phone`, `Device`, `Address`, `IP`, and `TaxID` nodes using relationships such as `OWNS`, `TRANSFER`, `PAID`, `LOCATED_IN`, `LISTED_ON`, and shared-identity relationships. The README documents the data model, setup, Cypher queries, and graph algorithms.

The demo seed data is synthetic. Do not load private, restricted, or personal information.

## Run locally

See the setup instructions in [README.md](./README.md). In brief: install requirements, configure FalkorDB in `.env`, seed the synthetic graph with `python aegisgraph.py seed`, and start the app with `uvicorn app.main:app --reload`.

## Repository

https://github.com/MaruvadaSaketh/AegisGraph-Agent

## AI-assistant disclosure

An AI coding assistant (Copilot SDK in VS Code) was used to help update project documentation, prepare the repository for submission, and verify the existing test suite. The project team should review and understand the implementation, graph model, queries, and technical decisions before presenting the project.

## Demo and deployment

Use the timed walkthrough in [DEMO-SCRIPT.md](./DEMO-SCRIPT.md) to record the demo, then add the video URL here before submitting. If no live deployment is available, use the complete local setup instructions in [README.md](./README.md).

**Demo video:** Add URL after recording.
