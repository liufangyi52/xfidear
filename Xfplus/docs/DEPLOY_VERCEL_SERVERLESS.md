# Vercel-Only Interview Demo Deployment

This deployment hosts the Vue frontend and FastAPI API in one Vercel project. It needs no Render account, card, or external backend URL.

## Important Limitation

The API database runs at `/tmp/xfidear-demo.db` inside a Vercel Serverless Function. It is available while a function instance stays warm, but Vercel can replace that instance at any time. New alerts, incident updates, and messages can therefore reset to the repository's demo data. This is suitable for an interview demonstration, not durable production storage.

## Deploy From Vercel

1. In Vercel, import `liufangyi52/xfidear` from the `main` branch.
2. Set **Root Directory** to the repository root. Do not use `Xfplus/frontend`, because the root contains the `/api/index.py` FastAPI function.
3. Set the framework preset to **Other**. The root `vercel.json` supplies the build command and output directory.
4. Do not set `VITE_API_BASE_URL`. The frontend calls `/api/...` on the same Vercel domain.
5. Deploy. Vercel installs `requirements.txt`, builds `Xfplus/frontend`, and creates the Python function from `api/index.py`.

## Smoke Test

1. Open `https://<your-project>.vercel.app/api/health`. It must return JSON with `"ok": true`.
2. Open `https://<your-project>.vercel.app/`.
3. Log in with `city_demo / 123456`.
4. Open the city command dashboard, alerts, and incident list.
5. Refresh a nested application page. The Vue SPA fallback should prevent a 404 response.

## Optional Environment Variables

No variables are required for the demonstration. Map, weather, and AI credentials can be added later in Vercel Project Settings -> Environment Variables. The default `FALLBACK_LLM_TYPE=mock` keeps the AI assistant usable without an external model key.
