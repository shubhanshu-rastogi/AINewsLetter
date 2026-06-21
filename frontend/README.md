# AI Newsletter — Operator Console (frontend)

A React + Vite + TypeScript single-page app for running and monitoring the
newsletter platform. It talks to the FastAPI backend over REST.

## What you can do

- **Trigger** a newsletter run with one click (Dashboard).
- **Watch live progress** — a progress bar + stage stepper update in real time as
  the run moves through collection → … → human review → publish (Run detail).
- **Review & decide** when a run pauses: approve & publish, request changes
  (with feedback that regenerates the draft), or reject.
- **Browse history** of every run and its outcome.
- **Manage configuration** from the UI (Settings): API keys (OpenAI / Anthropic /
  Beehiiv / LinkedIn / Notion), model names, and feature flags. Secrets are
  encrypted at rest by the backend and never shown again.

## Prerequisites

- Node.js 18+ and npm
- The backend running (see [`../backend/README.md`](../backend/README.md)). By
  default the dev server proxies to `http://localhost:8000`.

## Run it

```bash
cd frontend
npm install
cp .env.example .env        # optional; defaults proxy to localhost:8000
npm run dev                 # http://localhost:5173
```

Build for production:

```bash
npm run build               # outputs static files to dist/
npm run preview             # serve the built app locally
```

## Auth

If the backend has `REVIEW_AUTH_TOKEN` set, the app shows a login screen and
sends the token as `Authorization: Bearer <token>` on every request. If the
token is unset (local/dev), the app loads straight to the dashboard.

## Configuration

| Var | Purpose |
|---|---|
| `VITE_BACKEND_URL` | Backend the dev proxy forwards to (default `http://localhost:8000`). |
| `VITE_API_BASE` | Absolute API base; set when serving the built SPA separately from the API (skips the dev proxy). |

## Structure

```
src/
├── api.ts              # typed REST client + auth token handling
├── auth.tsx            # auth context (login/logout, required?-detection)
├── App.tsx             # routing + sidebar layout
├── components/
│   ├── RunState.tsx    # status badge, progress bar, stage stepper
│   └── DraftPreview.tsx# renders the generated newsletter content
└── pages/
    ├── Login.tsx
    ├── Dashboard.tsx   # trigger + recent runs
    ├── History.tsx     # all runs
    ├── RunDetail.tsx   # live progress + review actions + draft
    └── Settings.tsx    # config form (keys, models, flags)
```
