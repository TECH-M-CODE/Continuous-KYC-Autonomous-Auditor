# SentinelAI — API Contract

This OpenAPI-inspired contract defines the boundary between the React frontend and FastAPI backend.

## Global Concepts
- **Base URL**: `/api/v1`
- **Authentication**: Bearer Token (JWT) on all endpoints except `/auth/login` and `/health`.
- **Response Wrapper**: All 2xx and 4xx responses follow this exact schema:
  ```json
  {
    "success": boolean,
    "message": string,
    "data": object | array | null,
    "trace_id": string,
    "error_code": string | null
  }
  ```

---

## 1. Auth Module

### `POST /auth/login`
- **Request**: `{"email": "str", "password": "str"}`
- **Response Data**: `{"access_token": "str", "token_type": "bearer", "user": UserDTO}`
- **Errors**: `401 Unauthorized`

### `GET /auth/me`
- **Response Data**: `UserDTO`

---

## 2. Entities Module

### `GET /entities`
- **Query Params**: `page (int)`, `limit (int)`, `risk_band (str)`, `search (str)`
- **Response Data**: `PaginatedData<EntitySummaryDTO>`

### `GET /entities/{id}`
- **Response Data**: `EntityDetailDTO`
- **Errors**: `404 Not Found`

### `GET /entities/{id}/graph`
- **Description**: Returns data formatted explicitly for the React Flow Decision Graph.
- **Response Data**: `{"nodes": [DecisionNodeDTO], "edges": [DecisionEdgeDTO]}`

---

## 3. Alerts Module

### `GET /alerts`
- **Query Params**: `status (str)`, `priority (str)`, `assigned_to (uuid)`
- **Response Data**: `PaginatedData<AlertSummaryDTO>`

### `GET /alerts/{id}`
- **Response Data**: `AlertDetailDTO` (Includes embedded `InvestigationDTO`)

### `PATCH /alerts/{id}/action`
- **Request**: `{"action": "DISMISS" | "ESCALATE" | "RESOLVE", "reasoning": "str"}`
- **Response Data**: `AlertDetailDTO`
- **Errors**: `403 Forbidden` (if L1 Analyst tries to resolve Critical)

---

## 4. SAR (Suspicious Activity Reports) Module

### `GET /sars`
- **Query Params**: `status`
- **Response Data**: `PaginatedData<SARSummaryDTO>`

### `GET /sars/{id}`
- **Response Data**: `SARDetailDTO` (Includes citations and previous versions)

### `PUT /sars/{id}`
- **Description**: Creates a *new* version of the SAR draft.
- **Request**: `{"narrative": "str", "citations": [CitationDTO]}`
- **Response Data**: `SARDetailDTO` (version incremented)

### `POST /sars/{id}/decision`
- **Request**: `{"decision": "APPROVE" | "REJECT", "comments": "str"}`
- **Response Data**: `SARDetailDTO`

---

## 5. Audit Module

### `GET /audit/{entity_id}`
- **Response Data**: `PaginatedData<AuditEntryDTO>`

### `GET /audit/verify`
- **Description**: Validates the cryptographic hash chain of the entire audit log.
- **Response Data**: `{"is_valid": true, "broken_at_hash": null}`

---

## 6. Demo & Scenarios Module (Hackathon USP)

### `GET /demo/scenarios`
- **Response Data**: `[{"id": "money_laundering", "name": "Money Laundering", "description": "..."}]`

### `POST /demo/scenarios/{id}/trigger`
- **Description**: Executes a hardcoded script of events to simulate a complex compliance scenario in real-time.
- **Response Data**: `{"status": "running", "scenario_id": "str"}`

---

## 7. SSE Streaming

### `GET /stream`
- **Description**: Server-Sent Events connection.
- **Payload Format**: `{"event": "alert.new" | "risk.updated" | "scenario.progress", "data": {...}}`

---

## DTO Definitions

```typescript
// Shared
interface UserDTO { id: string; email: string; role: string; }

// Entities
interface EntitySummaryDTO { id: string; name: string; type: string; risk_score: number; risk_band: string; }
interface EntityDetailDTO extends EntitySummaryDTO {
  jurisdiction: string;
  peps: PersonDTO[];
  recent_events: RiskEventDTO[];
}

// Decision Graph
interface DecisionNodeDTO { id: string; type: 'news'|'match'|'policy'|'human'; data: { label: string; score_change?: number; date: string; }; position?: { x: number, y: number }; }
interface DecisionEdgeDTO { id: string; source: string; target: string; animated: boolean; label?: string; }

// Alerts
interface AlertSummaryDTO { id: string; entity_name: string; priority: string; status: string; created_at: string; }
interface AlertDetailDTO extends AlertSummaryDTO {
  investigation: {
    summary: string;
    evidence: { source: string; snippet: string; url: string; relevance: number }[];
  }
}

// SAR
interface SARDetailDTO { id: string; alert_id: string; version: number; status: string; narrative: string; citations: { source: string; context: string }[]; }
```
