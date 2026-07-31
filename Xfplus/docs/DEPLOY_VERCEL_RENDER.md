# Vercel + Render Deployment

This guide publishes the Vue frontend on Vercel and the FastAPI API on Render. It is intended for an interview demo and keeps the existing SQLite demo data and mock AI fallback.

## Before You Start

1. Push the `codex/vercel-render-deploy` branch to a GitHub repository you control.
2. Do not commit `.env`, API keys, or service tokens. Add them only in the Vercel or Render environment-variable screens.
3. The repository contains `render.yaml` at its root. It defines the Render service with `Xfplus` as the service root directory.

## 1. Deploy the API to Render

1. Open Render, choose **New** -> **Blueprint**, and select the GitHub repository.
2. Render reads `render.yaml` and creates `zjj-smart-emergency-api`.
3. In the service environment settings, leave `FALLBACK_LLM_TYPE=mock` for a reliable demo. Add optional map, weather, or AI keys only when available.
4. Deploy the service. Copy its public HTTPS URL, for example `https://your-api.onrender.com`.
5. Open `https://your-api.onrender.com/api/health`. The response must include `"ok": true`.

## 2. Deploy the Frontend to Vercel

1. Open Vercel, choose **Add New** -> **Project**, and import the same GitHub repository.
2. Set **Root Directory** to `Xfplus/frontend`.
3. Keep the build command as `npm run build` and output directory as `dist`.
4. Add the environment variable `VITE_API_BASE_URL` with the Render URL from step 1, without a trailing slash. Example: `https://your-api.onrender.com`.
5. Deploy and copy the Vercel HTTPS URL, for example `https://your-project.vercel.app`.

## 3. Connect CORS and Redeploy

1. Return to Render environment settings.
2. Set `FRONTEND_ORIGIN` to the exact Vercel URL, for example `https://your-project.vercel.app`, without a trailing slash.
3. Redeploy Render so FastAPI accepts requests from the frontend.

## Smoke Test

1. Open the Render health endpoint: `<render-url>/api/health`.
2. Open the Vercel URL and refresh a nested page after navigation. Vercel should continue to serve the Vue app instead of returning 404.
3. Log in with `city_demo / 123456`.
4. Open the command dashboard and view the alert or incident list.
5. For a second role check, sign in as `resident_demo / 123456` and view alerts or the risk map.

## Data and Security

- SQLite is appropriate for this interview demonstration. Render instances without a persistent disk can lose newly created records after a restart; the application's seeded demo data is recreated at startup.
- Use a Render persistent disk or move to PostgreSQL before treating this as durable production storage.
- Keep `VITE_API_BASE_URL`, `FRONTEND_ORIGIN`, map keys, weather keys, and AI credentials in service environment settings. Never add them to source control.
