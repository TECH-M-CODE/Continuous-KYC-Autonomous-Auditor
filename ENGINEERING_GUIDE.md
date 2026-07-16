# Engineering Guide

This document defines the engineering contracts, layouts, standards, and strategies that dictate all implementation phases of CXKYC.

## 1. Folder Structure
```text
TECHM/                              # Monorepo Root
├── .env.example                    # Environment variable template
├── backend/                        # Backend Application (FastAPI + Python)
│   ├── app/                        # Application Source Code
│   │   ├── adapters/               # Data Ingestion Adapters
│   │   ├── agents/                 # AI Reasoning Layer (LangGraph)
│   │   ├── api/                    # API Controllers
│   │   ├── domain/                 # Domain Models (Core)
│   │   ├── infrastructure/         # External System Wrappers (Chroma, LLM)
│   │   ├── repositories/           # Data Access Layer
│   │   ├── schemas/                # Pydantic DTOs
│   │   └── services/               # Business Logic Orchestration
│   ├── data/                       # Local SQLite and Chroma stores
│   └── tests/                      # Backend Test Suite
├── frontend/                       # React Application
│   ├── src/
│   │   ├── api/                    # Axios instances and hooks
│   │   ├── components/             # Reusable UI widgets
│   │   ├── pages/                  # Route views
│   │   └── App.jsx                 # Entrypoint
└── scripts/                        # Utility scripts
```

## 2. API Contract
- **Base URL**: `/api/v1`
- **Response Wrapper**: All JSON responses use a standard wrapper:
  `{"success": bool, "message": str, "data": any, "trace_id": str}`
- **Entities**: 
  - `GET /entities` (List entities with pagination)
  - `GET /entities/{id}/graph` (ReactFlow decision traces)
- **Alerts**:
  - `GET /alerts` (Queue)
  - `GET /alerts/stream` (SSE real-time push)
  - `PATCH /alerts/{id}` (Dismiss/Escalate)
- **SARs**:
  - `GET /sar` (Pending/Approved reports)
  - `POST /sar/{id}/approve`

## 3. Domain Model
- `Entity`: Central KYC profile (`id`, `name`, `risk_score`, `risk_band`, `watched`).
- `RawEvent`: Unprocessed incoming signal (`hash`, `source`, `text`).
- `Alert`: A triggered threshold breach requiring attention (`entity_id`, `severity`, `status`).
- `SAR`: A formal Suspicious Activity Report (`narrative`, `citations`, `officer_notes`).
- `AuditLog`: Immutable event record (`action`, `actor`, `hash`).

## 4. DTOs (Data Transfer Objects)
All data crossing the network boundary must be serialized via Pydantic models (Backend) and parsed into matching TypeScript interfaces/Zod schemas (Frontend).
Example: `EntitySummaryDTO`, `DecisionNodeDTO`, `AlertStreamEventDTO`.

## 5. Engineering Contract
- **Controllers (API)**: Must contain zero business logic. They handle HTTP only.
- **Services**: Orchestrate the business logic, interacting with the database through repositories.
- **Repositories**: Exclusively handle SQLAlchemy/ChromaDB persistence logic.
- **Agents**: Handle LLM operations, shielded behind an `LLMGateway` that handles retries, caching, and degradations.

## 6. Implementation Plan
We develop in vertical slices:
1. **Foundation**: Database, Models, Repositories.
2. **Ingestion**: Adapters, raw event storage.
3. **Intelligence**: LangGraph agent pipeline, semantic retrieval (RAG).
4. **UX**: Dashboard, Live Feeds, ReactFlow graphs.
5. **Auditing**: Hash-chained logging layer.

## 7. Deployment
CXKYC is designed to run in containers.
- **Database**: SQLite mounted via Docker volume (or swapped to PostgreSQL via env vars).
- **Vector DB**: ChromaDB running embedded or standalone container.
- **Backend**: Uvicorn running FastAPI.
- **Frontend**: Nginx serving the static Vite build.

## 8. Environment Variables
- `DATABASE_URL`: Connection string.
- `CHROMA_PERSIST_DIR`: Path to vector storage.
- `GEMINI_API_KEY`: Secrets for the LLM Gateway.
- `VITE_API_BASE_URL`: Frontend configuration pointing to the backend.

## 9. Git Strategy
- **Trunk-based development**: All work is merged frequently into `dev`.
- **Commit Format**: Descriptive messages (e.g. `feat: add decision tree`, `fix: resolve merge conflicts`).
- **No force pushing** unless explicitly rewriting history for sanitization (e.g. removing large files or secrets).

## 10. Testing
- **Backend**: Pytest suite covering adapters, agents (using `MockLLMClient`), api, pipeline, and repositories.
- **Integration**: Testing the `lifespan` event logic, RAG pipelines, and database constraints.
