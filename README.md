# DayLight (CLB)
SpartaHack 2026

## Run locally

Backend:

```bash
cd clb-app/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd clb-app/frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Notes
- Google Calendar and Presage integrations are mocked for the hackathon MVP.
- Set `USE_MOCK_DATA=false` in `clb-app/backend/.env` if you wire real OAuth.
