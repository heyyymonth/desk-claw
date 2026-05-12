# Frontend

React + TypeScript + Vite workflow UI. The frontend calls FastAPI only and never calls Ollama.

Set `VITE_ADMIN_API_KEY` only for local admin telemetry inspection. It is sent to the backend as `X-DeskAI-Admin-Key` for the AI Technical Dashboard until real login/session auth replaces the V0 admin key.

## Commands

```bash
npm install
npm run dev
npm test
```
