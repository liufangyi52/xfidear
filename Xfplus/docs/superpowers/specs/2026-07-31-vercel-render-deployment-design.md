# Vercel and Render Deployment Design

## Goal

Publish the existing Vue frontend and FastAPI backend as separately hosted HTTPS services so an interviewer can open one Vercel URL and exercise the application.

## Deployment Architecture

Vercel builds `Xfplus/frontend` and serves the Vue single-page application. The frontend receives the public FastAPI origin through `VITE_API_BASE_URL`; API requests therefore go directly to Render rather than relying on Vite's local `/api` proxy.

Render starts the FastAPI application from `Xfplus/backend`. Its health endpoint remains `GET /api/health`. The backend allows only the configured frontend origin through `FRONTEND_ORIGIN`, while existing local development origins remain available for local use.

```
Browser -> Vercel Vue SPA -> Render FastAPI -> SQLite demo database
```

## Components

- `Xfplus/frontend/src/api.ts`: preserves relative API requests for local development and uses `VITE_API_BASE_URL` when it is supplied by Vercel.
- `Xfplus/frontend/vercel.json`: rewrites client-side routes to `index.html` so direct visits and refreshes work.
- `Xfplus/backend/render.yaml`: defines the Render web service build and start commands and its health-check path.
- `Xfplus/.env.example`: documents deployment-only environment variables without containing credentials.
- `Xfplus/docs/DEPLOY_VERCEL_RENDER.md`: gives the exact GitHub, Render, and Vercel setup sequence and validation steps.

## Configuration

Vercel requires `VITE_API_BASE_URL=https://<render-service>.onrender.com` at build time. Optional map keys remain Vercel environment variables.

Render requires `FRONTEND_ORIGIN=https://<vercel-project>.vercel.app` and a writable `DATABASE_URL`. API keys remain optional because the application supports its existing mock AI and data fallbacks. No secret is added to version control.

## Data and Failure Behavior

SQLite is retained for the interview demo. A Render service without a persistent disk may lose records created during a demo after a restart; seed data and demo accounts are recreated by the existing startup process. The deployment guide will state that PostgreSQL or a Render persistent disk is required for durable production data.

The frontend's existing API error handling remains unchanged. A wrong backend URL produces its current request error states instead of silently falling back to mock data.

## Verification

- Frontend production build succeeds using a deployment-style `VITE_API_BASE_URL`.
- The Render start command imports and serves the FastAPI health endpoint.
- A static hosting rewrite test confirms that a Vue route resolves to `index.html`.
- The deployment guide contains login credentials and smoke tests for health, login, routing, and CORS.

## Scope Limits

This change makes the repository ready to deploy. It does not create cloud services, push code to GitHub, configure user secrets, register a custom domain, or migrate SQLite to PostgreSQL.
