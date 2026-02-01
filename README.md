# DayLight (CLB)

Cognitive Load Budgeting - A smart calendar that helps you manage your mental energy.

## Quick Start (Docker)

The recommended way to run the full stack with the Presage SmartSpectra SDK:

```bash
cd clb-app/backend

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your SMARTSPECTRA_API_KEY

# Start all services
docker-compose up --build
```

This starts:
- **Python Backend** (FastAPI) on `http://localhost:8000`
- **Presage Daemon** (C++ SmartSpectra SDK) - internal only

Then start the frontend:

```bash
cd clb-app/frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Run Locally (Development)

For development without Docker (uses simulated data):

**Backend:**
```bash
cd clb-app/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd clb-app/frontend
npm install
npm run dev
```

## Architecture

```
┌─────────────┐     WebSocket      ┌─────────────┐       TCP        ┌─────────────────┐
│   Frontend  │◄──────────────────►│   Python    │◄────────────────►│  Presage Daemon │
│   (React)   │                    │   Backend   │                  │  (SmartSpectra) │
└─────────────┘                    └─────────────┘                  └─────────────────┘
```

- **Frontend**: React + Vite, sends video frames via WebSocket
- **Backend**: FastAPI, manages sessions, calculates cognitive load scores
- **Presage Daemon**: C++ service with SmartSpectra SDK for vital signs detection

## Environment Variables

Copy `clb-app/backend/.env.example` to `.env` and configure:

| Variable | Description |
|----------|-------------|
| `SMARTSPECTRA_API_KEY` | Required for real vital signs detection |
| `GOOGLE_CLIENT_ID` | For Google Calendar integration |
| `GOOGLE_CLIENT_SECRET` | For Google Calendar integration |
| `USE_MOCK_DATA` | Set to `false` to use real integrations |

## Documentation

- **[Presage Protocol](clb-app/backend/PRESAGE_PROTOCOL.md)** - Session control protocol and API reference
- **API Docs**: `http://localhost:8000/docs` (when backend is running)

## Key Features

- **Sage Mode**: Real-time vital signs monitoring during tasks
- **Cognitive Load Budgeting**: Track mental energy costs of events
- **Personalized Baselines**: Learns your resting vitals over time
- **Calendar Integration**: Import events from Google Calendar

## Notes

- SmartSpectra SDK only runs on Linux (amd64). Docker handles this automatically.
- First-time Docker build may take 5-10 minutes to install SDK dependencies.
- Baseline calibration requires ~5 complete sessions for accurate personalization.
