# Continuous KYC Autonomous Auditor (CXKYC)
**Final Project Report**

## Abstract
The Continuous KYC Autonomous Auditor (CXKYC) addresses the highly manual, error-prone, and point-in-time nature of traditional Anti-Money Laundering (AML) and Know Your Customer (KYC) auditing. By employing an Event-Driven Architecture and a Multi-Agent LLM network, CXKYC continuously screens entities against live news, fraud, and sanctions feeds, automatically resolving entities, scoring risk deterministically, and drafting Suspicious Activity Reports (SARs) with human-in-the-loop oversight.

## Problem Statement
Compliance teams suffer from "alert fatigue" due to inflexible rules engines that generate overwhelming numbers of false positives. Traditional KYC is a static, periodic process, meaning an entity's risk profile becomes outdated the moment it is approved. When high-risk events (like sudden sanctions or adverse media exposure) occur, manual investigators take days to synthesize evidence and file SARs, exposing institutions to severe regulatory penalties.

## Objectives
1. Shift KYC from a static, point-in-time check to a continuous, real-time process.
2. Filter out false positives intelligently before they reach a human investigator.
3. Automatically assemble evidence and draft compliance reports (SARs) to accelerate human review.
4. Maintain a mathematically verifiable, tamper-evident audit log for regulators.
5. Keep a "Human in the loop" to ensure all final reporting decisions are made by responsible compliance officers, not AI.

## Our Approach
We built a highly scalable pipeline consisting of three concurrent loops:
- **Ingestion**: Scalable feed adapters pull data, strip noise, and hash content to prevent duplicate processing.
- **Agent Intelligence**: Events pass a rapid fuzzy-match pre-filter. Surviving events are routed through a LangGraph agent network:
  - *Resolver*: Semantically matches unstructured news text to specific database entities using RAG.
  - *Investigator*: Extracts deep context and flags.
  - *Reporter*: Drafts SARs for critical breaches.
- **Human Review**: A React-based dashboard allows compliance officers to see live feeds, review the AI's logic (via Decision Graphs), and formally approve/reject SARs.

## Novelty
- **Explainability by Construction**: We do not let the LLM guess a risk score. The LLM classifies the severity, and a deterministic mathematical engine applies weights based on `policy.yaml`. 
- **Two-Stage Screening**: We avoid astronomical API costs by using `rapidfuzz` to eliminate 95% of events locally, only invoking the LLM for ambiguous or high-confidence matches.
- **Append-Only Audit**: Both human and AI actions are securely chained. 

## Architecture
CXKYC is designed with strict separation of concerns:
- **Frontend**: Vanilla JS, React, Server-Sent Events (SSE).
- **Backend**: FastAPI, handling routing and database sessions.
- **Agent Layer**: LangGraph + Google Gemini via a centralized LLM Gateway with degradation ladders and caching.
- **Vector DB**: ChromaDB for regulatory compliance (RAG) and entity resolution.
- **Relational DB**: SQLite (WAL mode) tracking events, entities, alerts, and audit logs.

## Team Contribution
*(Fill in team member names and specific roles/contributions here)*
- **Member 1**: Backend architecture, Multi-agent LangGraph integration.
- **Member 2**: Frontend UI/UX, Decision Graph visualization.
- **Member 3**: Data pipelines, RAG setup, and LLM prompt engineering.

## Tools & Technologies
- **Python 3.11+, FastAPI**
- **LangGraph, Google Gemini**
- **ChromaDB, SQLAlchemy, SQLite**
- **React, ReactFlow, Vanilla CSS**
- **Nvidia AI Endpoints, Docker**

## Datasets Used
- **Synthetic KYC Dataset**: Generated profiles with varying risk levels (Low, Medium, High).
- **Financial Fraud Data**: `fraud.csv` and `nonfraud.csv` containing adverse media.
- **Sanctions Lists**: Live OFAC/OpenSanctions feeds.

## Results
The system successfully digests high volumes of raw textual data, accurately mapping fuzzy entity names to exact customer profiles. It dynamically adjusts risk scores, escalates critical alerts in real-time to the dashboard via SSE, and produces high-quality, legally-grounded SAR drafts that save compliance officers hours of manual investigation time.

## Future Scope
- **Scalability**: Migrate from SQLite to PostgreSQL and replace APScheduler with Kafka consumers for true distributed processing.
- **Advanced Topology**: Introduce a Network Agent to traverse complex UBO (Ultimate Beneficial Owner) graphs and detect nested shell-company risk.
- **Feed Integrations**: Connect directly to premium data feeds like Dow Jones Risk & Compliance or Refinitiv World-Check.

## Conclusion
CXKYC proves that LLMs can be safely integrated into heavily regulated financial environments. By strictly scoping the AI's role to semantic reasoning while leaving mathematics and final judgments to deterministic engines and human professionals, we deliver massive efficiency gains without sacrificing compliance integrity.
