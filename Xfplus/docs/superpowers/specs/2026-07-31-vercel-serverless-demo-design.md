# Vercel Serverless Demo Design

## Goal

Deploy the Vue application and its existing FastAPI API on one Vercel project without Render, using the existing seeded SQLite data for interview demonstrations.

## Architecture

Vercel builds the frontend from `Xfplus/frontend`. Requests beginning with `/api/` are routed to a Python Serverless Function that imports the existing FastAPI application. All other requests are served by the Vue build and fall back to `index.html` for client-side routes.

The serverless function sets `DATABASE_URL` to a SQLite file under `/tmp`. Each warm function instance preserves actions made during its lifetime. A new instance initializes the existing seed data again, so this is deliberately non-persistent.

```
Browser -> Vercel Vue static output
        -> /api/* -> Vercel Python Function -> /tmp SQLite seeded demo data
```

## Components

- Repository-root `api/index.py`: adds `Xfplus` to Python imports, sets the temporary database URL before importing the FastAPI app, and exports the ASGI application for Vercel.
- Repository-root `requirements.txt`: exposes the existing FastAPI requirements to Vercel's Python build.
- Repository-root `vercel.json`: runs the frontend build, routes `/api/*` to the Python function, and routes Vue URLs to the SPA entry point.
- `Xfplus/backend/config.py`: uses a Vercel-aware temporary SQLite URL only when Vercel sets its runtime environment; local and Render configuration behavior stays unchanged.
- Deployment tests and documentation: verify the Vercel descriptor and describe the temporary-data constraint.

## Request and Data Flow

The current frontend uses an empty `VITE_API_BASE_URL` by default, so API calls remain same-origin on Vercel. Authentication, alerts, incidents, messages, map data, and mock AI use the existing FastAPI routers unchanged.

The startup hook initializes tables and seed records. No external database, card, API key, or backend host is required for the demo. API mutations are accepted while the function instance is warm; they reset when Vercel replaces the instance.

## Error Handling

The function uses the current API error responses. If the temporary database cannot be initialized, the health route and API requests return server errors rather than using untracked client-side data. External map, weather, and AI keys remain optional because the application already provides fallback behavior.

## Verification

- Unit tests assert the Vercel function exports the FastAPI app and forces a `/tmp` SQLite URL under Vercel.
- Descriptor tests assert API routing precedes SPA fallback.
- The frontend production build succeeds without `VITE_API_BASE_URL`, preserving same-origin API requests.
- Local FastAPI health check uses the Vercel-compatible entry point with `VERCEL=1`.

## Scope Limits

This design is for an interview demo. It does not provide durable records, background jobs, WebSocket reliability, external messaging delivery, custom domains, or production database migrations. Durable production data would require a managed database outside the Vercel function filesystem.
