# SENT1NEL — Local Startup Guide

## Prerequisites

- Docker + Docker Compose
- Python 3.10+ with a virtual environment
- Node.js 20+

---

## 1. Start Infrastructure (Docker)

From the project root:

```bash
docker compose up -d nats timescaledb redis
```

Wait for all three to be healthy (takes ~10–15s):

```bash
docker compose ps
```

All three should show `healthy` before proceeding.

---

## 2. Start the Backend

Activate your virtualenv and run the Python backend:

```bash
source .venv/bin/activate         # or: source venv/bin/activate
python -m sentinel
```

The API will be available at `http://localhost:8000`.

Confirm it's up:

```bash
curl http://localhost:8000/health
```

> **Note:** On first run TimescaleDB runs migrations automatically. If the backend exits immediately, wait a few more seconds for the DB to finish initializing and retry.

---

## 3. Start the Frontend Dev Server

In a separate terminal, from the project root:

```bash
cd frontend
npm install       # only needed on first run or after dependency changes
npm run dev
```

The UI will be at `http://localhost:3000`.

---

## Startup Order (Critical)

```
Docker infra  →  Python backend  →  Vite dev server
```

The backend will crash if NATS/TimescaleDB/Redis aren't ready. Always start infra first.

---

## Stopping Everything

```bash
# Kill the backend (Ctrl+C in its terminal, or:)
pkill -9 -f "python -m sentinel"

# Kill the frontend (Ctrl+C in its terminal, or:)
pkill -9 -f vite

# Stop Docker services
docker compose down
```

To wipe all persisted data (DB, NATS, Redis) on next start:

```bash
docker compose down -v
```

---

## Ports at a Glance

| Service       | Port  |
|---------------|-------|
| Frontend      | 3000  |
| Backend API   | 8000  |
| NATS client   | 4222  |
| NATS monitor  | 8222  |
| TimescaleDB   | 5432  |
| Redis         | 6380  |

---

## Live Data Sources

| Domain      | Source                     | Notes                              |
|-------------|----------------------------|------------------------------------|
| Aircraft    | OpenSky ADS-B              | Requires `OPENSKY_USER/PASS` in `.env` |
| Vessels     | AISStream                  | Requires `AISSTREAM_API_KEY` in `.env` |
| Satellites  | CelesTrak TLE + SGP4       | No auth needed                     |
| Earthquakes | USGS GeoJSON feed          | No auth needed                     |
| Weather     | Open-Meteo                 | No auth needed                     |
| Geopolitics | Simulated (30–90s interval)| Built-in                           |

Copy `.env.example` to `.env` and fill in any API keys you have. The app runs without them — those connectors will just be inactive.

---

## Useful Endpoints

```
GET  /health                    — backend liveness
GET  /api/v1/entities/live      — all live tracked entities (JSON)
GET  /api/v1/entities/tracks    — track list with counts
WS   /ws/entities               — live entity stream (JSON frames)
WS   /ws/events                 — live event stream (JSON frames)
GET  /metrics                   — Prometheus metrics
```
