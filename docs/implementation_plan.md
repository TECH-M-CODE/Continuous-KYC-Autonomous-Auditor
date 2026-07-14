# Implementation Plan: SentinelAI Hackathon & Dependency Strategy

This plan incorporates the massive strategic upgrades suggested for the Hackathon environment (Mocks, Scenario Engine, Verification, Decision Graphs) and establishes a highly parallel execution roadmap.

## 1. Architectural Strategy Shifts (The "Hackathon Edge")

### Infrastructure Simplification
- **No Redis / No Vault**: We will implement `AsyncioBroker`, `LocalMemoryCache`, and `EnvSecretsManager` immediately. They will implement the strict `I...` interfaces, guaranteeing production-readiness without DevOps overhead.

### Bounded Contexts Added
- **`knowledge/`**: Dedicated to RAG. `dataset_loader.py`, `chunker.py`, `embedder.py`, `retriever.py`, `knowledge_service.py`.
- **`verification/`**: The "Fake News" isolation layer. `credibility.py`, `fact_checker.py`, `source_ranker.py`.
- **`explainability/`**: Traceability layer. `decision_trace.py`, `reason_builder.py`, `citation_builder.py`.
- **`demo/`**: The "Demo Gold". Hardcoded `scenario_engine.py` with scripted cases (`money_laundering_case.py`).

### Risk Engine Evolution
- Shift from monolithic `score_delta` to: `Rule Engine -> Confidence Engine -> Evidence Engine -> Policy Engine -> Decision Builder`.

### Frontend Pivot
- Replace basic `Timeline` with an interactive, animated **React Flow Decision Graph**.

---

## 2. Dependency Analysis

To achieve zero merge conflicts, we must map exactly what depends on what.

| Module | Prerequisites (Must build first) | Consumes Interfaces | Exposes Interfaces |
|--------|----------------------------------|---------------------|--------------------|
| **Domain Models** | None | None | Base Entities, Enums |
| **Interfaces (Contracts)** | Domain Models | None | `IUnitOfWork`, `I...Repo`, `IBroker` |
| **Infrastructure (Mocks)**| Interfaces | None | Implements `IBroker`, `ICache` |
| **Database/Repositories** | Interfaces, Infrastructure | None | Implements `I...Repo`, `IUnitOfWork` |
| **Knowledge Engine** | Infrastructure | `VDB` | `IKnowledgeService` |
| **Verification Engine**| Infrastructure, LLM Gateway | `LLM` | `IVerificationService` |
| **Risk & Engines** | Domain, Interfaces | `IUnitOfWork` | `IRiskEngine`, `IPolicyEngine` |
| **Agents / LangGraph**| Knowledge, Verification, Risk| `IKnowledge`, `IVerification` | `AgentState` outputs |
| **Demo / Scenarios** | Agents, Repositories | `IUnitOfWork`, `IBroker`| Scenario Trigger API |
| **API Controllers** | Everything above | All Services | OpenAPI JSON |
| **Frontend UI** | API Contract (JSON) | OpenAPI JSON | React Components |

---

## 3. Five-Developer Parallel Roadmap

Because we have frozen the **Canonical Domain Model** and the **API Contract**, the team can work completely in parallel.

### Sprint 1: Foundation (Day 1 - Morning)
*The project is runnable after this sprint (passing Healthchecks).*
- **Dev 1 (Data Layer)**: Implement SQLite Repositories & UnitOfWork (`app/repositories/`).
- **Dev 2 (Infra Mocks)**: Implement `AsyncioBroker`, `LocalMemoryCache`, `LLMGateway` (`app/infrastructure/`).
- **Dev 3 (Knowledge)**: Build `knowledge/` chunker, embedder, and mock retriever.
- **Dev 4 (API Shell)**: Scaffold FastAPI controllers returning hardcoded JSON matching the API Contract.
- **Dev 5 (Frontend Shell)**: Initialize React/Vite, Tailwind, and React Router. Create empty page layouts.

### Sprint 2: Core Engines (Day 1 - Afternoon)
*The project is runnable (Data flows end-to-end).*
- **Dev 1 (Risk Engine)**: Implement Rule, Confidence, and Policy engines (`app/services/scoring/`).
- **Dev 2 (Verification)**: Implement `verification/` (Fact Checking, Credibility scoring).
- **Dev 3 (Explainability)**: Implement `explainability/` (Decision trace generation).
- **Dev 4 (Ingestion/Adapters)**: Wire external feeds to the `AsyncioBroker` -> Database.
- **Dev 5 (Frontend UI)**: Build the React Flow Decision Graph component using dummy data.

### Sprint 3: Agents & Scenarios (Day 2 - Morning)
*The project is runnable (AI is alive).*
- **Dev 1 (Agents)**: Hook up LangGraph AuditorState to the Knowledge and Verification engines.
- **Dev 2 (Demo Gold)**: Build `demo/scenario_engine.py` and script the `money_laundering.py` demo.
- **Dev 3 (Audit/SAR)**: Implement Hash-chaining (`audit_service.py`) and SAR generation logic.
- **Dev 4 (API Wiring)**: Connect FastAPI controllers to actual Services instead of hardcoded JSON.
- **Dev 5 (Frontend State)**: Connect UI to API via Axios/React Query. Wire up SSE connection.

### Sprint 4: Polish & Pitch (Day 2 - Afternoon)
- **All Devs**: Bug bashing, UX polish, scenario rehearsal. No new features.

---

> [!IMPORTANT]
> **User Review Required**:
> The Domain Model, API Contract, and this Implementation Plan are now documented as artifacts. 
> Please review and approve this overarching architecture and roadmap. Once approved, we will begin execution, starting with generating the actual Python code for these bounded contexts and mock infrastructure.
