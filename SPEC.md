# SPEC.md — Frontend ↔ Backend Contract

> **This document is the source of truth for the API contract.** Locked after Day 1 morning sync. Changes require both Ibra and Asha to agree in WhatsApp.

> **Day 2 correction:** earlier revisions of this file documented a non-existent URL pattern (`POST /apps/.../sessions/.../run_sse`). The real ADK routes were verified against `GET /openapi.json` on the running server. The corrected routes are below. App name is the **directory name** (`marketing_agents`), not the orchestrator agent's `name` field (`marketing_orchestrator`).

## App name

ADK routes apps by their **directory name** under the project root. The agent module is at `marketing_agents/agent.py`, so:

```
appName = "marketing_agents"
```

The orchestrator agent's `name="marketing_orchestrator"` is an internal display/delegation label — it is **not** a URL component.

## Base URL

`BASE_URL`:
- Local dev: `http://localhost:8001`
- Production: `https://hack2skill-778200673789.asia-southeast1.run.app`

Frontend resolves this dynamically based on `window.location.hostname`.

## Session bootstrap (required before first query)

ADK rejects `/run_sse` with a 500 if the session does not exist. The frontend must create the session once on page load:

```
POST {BASE_URL}/apps/marketing_agents/users/u1/sessions/{sessionId}
Content-Type: application/json

{}
```

`sessionId` is generated once on page load via `crypto.randomUUID()` and reused for the rest of the session.

Expected response: `200 OK` with the session record. If non-200, surface the error to the user and block sends.

## SSE query endpoint

```
POST {BASE_URL}/run_sse
Content-Type: application/json
```

Note: `/run_sse` is a **top-level route**, not nested under `/apps/...`. The body carries the routing info.

## Request body

```json
{
  "appName": "marketing_agents",
  "userId": "u1",
  "sessionId": "{sessionId}",
  "newMessage": {
    "role": "user",
    "parts": [{ "text": "[tone:executive] What were yesterday's top campaigns?" }]
  }
}
```

## Audience tone convention

The user's prompt is prefixed with one of three tone tags:

- `[tone:executive]` — high-level, business outcomes, no jargon (default)
- `[tone:technical]` — metrics, methods, SQL exposed, full detail
- `[tone:client]` — friendly, summary-only, no internal context

The agent's system prompt parses the prefix and adjusts output style. The schema (card vs battlecard) does not change between tones — only the *content* style does.

## Response structure

Agent returns text containing a JSON code block. Frontend parses the **first** ` ```json ... ``` ` block in the response (regex: `/```json\s*([\s\S]*?)\s*```/` — tolerant to missing leading/trailing whitespace).

Three response types:

### Type: `card` (most common)

```json
{
  "type": "card",
  "headline": "Revenue dropped 18% in Q3",
  "metrics": [
    { "label": "Revenue", "value": "$4.2M", "delta": "-18%" },
    { "label": "MoM change", "value": "-$920K" }
  ],
  "insight": "The drop correlates with a 32% rise in mobile bounce rate after the Sept 14 release.",
  "action": "Review mobile performance metrics",
  "sql_queries": [
    "SELECT date, revenue FROM daily_metrics WHERE quarter = 'Q3'"
  ]
}
```

**Field rules:**

| Field | Required | Notes |
|---|---|---|
| `headline` | Yes | 1 sentence, max 80 chars |
| `metrics` | Yes | Array of 1–4 items |
| `metrics[].label` | Yes | Short label, e.g. "Revenue" |
| `metrics[].value` | Yes | The metric value as string |
| `metrics[].delta` | No | Change indicator like "+12%" or "-5%" |
| `insight` | Yes | 1–3 sentences |
| `action` | Yes | Imperative phrase, e.g. "Review X" |
| `sql_queries` | No | Array of SQL strings from tool calls |

### Type: `battlecard` (competitive queries)

```json
{
  "type": "battlecard",
  "subjects": [
    {
      "name": "Improvado",
      "metrics": [
        { "label": "Pricing", "value": "$2K-3K/mo" },
        { "label": "Customers", "value": "1000+" }
      ],
      "strengths": [
        "500+ data connectors",
        "Mature ETL platform since 2017"
      ],
      "weaknesses": [
        "Single-domain (analytics only)",
        "Enterprise-only pricing"
      ]
    },
    {
      "name": "Triple Whale",
      "metrics": [
        { "label": "Pricing", "value": "$100-600/mo" },
        { "label": "Focus", "value": "DTC e-commerce" }
      ],
      "strengths": [
        "Strong attribution for Shopify brands",
        "Conversational AI ('Moby') for queries"
      ],
      "weaknesses": [
        "Limited beyond e-commerce",
        "Single-domain"
      ]
    }
  ],
  "sql_queries": []
}
```

**Field rules:**

| Field | Required | Notes |
|---|---|---|
| `subjects` | Yes | Exactly 2 items |
| `subjects[].name` | Yes | Competitor or comparison subject name |
| `subjects[].metrics` | Yes | 1–4 items, same shape as card metrics |
| `subjects[].strengths` | Yes | 2–4 bullet strings |
| `subjects[].weaknesses` | Yes | 2–4 bullet strings |
| `sql_queries` | No | Same as card |

### Type: text fallback

If the agent fails to produce a valid card or battlecard, it returns plain text without a JSON block. Frontend renders it as a regular text message bubble.

## SQL logging requirement (backend)

Every tool function in `marketing_agents/tools.py` must:

1. Build the SQL query string before executing
2. Log it (`print(f"[SQL] {query}")`)
3. Return both the result AND the query in the response: `{"result": ..., "sql": "SELECT ..."}`
4. The agent aggregates all SQL queries from tool calls into the `sql_queries` field of its final response

## Locked features (5 total)

| # | Feature | Owner |
|---|---|---|
| 1 | Blueprint template buttons | Asha (frontend only) |
| 2 | Audience toggle dropdown | Both (Ibra prompt + Asha UI) |
| 3 | Response card rendering | Both (Ibra schema + Asha render) |
| 4 | Query Viewer side panel | Both (Ibra logs SQL + Asha displays) |
| 5 | Battlecard format | Both (Ibra agent mode + Asha render) |

**No new features added during the sprint.** Polish only after these 5 are working end-to-end.
