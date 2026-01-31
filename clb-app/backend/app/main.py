from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routers import budget, calendar, events, optimize, presage, recovery, team
from app.utils.mock_data import generate_mock_week, generate_team_metrics

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed data
    app.state.events = generate_mock_week()
    app.state.team_metrics = generate_team_metrics()
    app.state.sage_sessions = {}
    app.state.oauth_tokens = {}
    yield
    # Shutdown: cleanup (none needed for in-memory)


app = FastAPI(title="CLB Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(calendar.router, prefix="/api", tags=["calendar"])
app.include_router(events.router, prefix="/api", tags=["events"])
app.include_router(budget.router, prefix="/api", tags=["budget"])
app.include_router(optimize.router, prefix="/api", tags=["optimize"])
app.include_router(recovery.router, prefix="/api", tags=["recovery"])
app.include_router(presage.router, prefix="/api", tags=["presage"])
app.include_router(team.router, prefix="/api", tags=["team"])
