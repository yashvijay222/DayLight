import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routers import baseline, budget, calendar, events, optimize, presage, recovery, team
from app.routers.presage import get_presage_client
from app.utils.mock_data import generate_mock_week, generate_team_metrics

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def auto_connect_presage():
    """Automatically connect to the Presage daemon on startup."""
    client = get_presage_client()
    
    # Give the presage container time to start
    max_attempts = 10
    for attempt in range(max_attempts):
        if client.connect():
            logger.info("Connected to Presage daemon on startup")
            return True
        logger.info(f"Waiting for Presage daemon... attempt {attempt + 1}/{max_attempts}")
        await asyncio.sleep(2)
    
    logger.warning("Could not connect to Presage daemon - will retry on demand")
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed data
    logger.info("Starting DayLight Backend...")
    app.state.events = generate_mock_week()
    app.state.team_metrics = generate_team_metrics()
    app.state.sage_sessions = {}
    app.state.oauth_tokens = {}
    
    # Auto-connect to Presage daemon (non-blocking)
    asyncio.create_task(auto_connect_presage())
    
    logger.info("DayLight Backend started successfully")
    yield
    
    # Shutdown: cleanup
    logger.info("Shutting down DayLight Backend...")
    client = get_presage_client()
    client.disconnect()
    logger.info("DayLight Backend shutdown complete")


app = FastAPI(title="CLB Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(baseline.router, prefix="/api", tags=["baseline"])
app.include_router(calendar.router, prefix="/api", tags=["calendar"])
app.include_router(events.router, prefix="/api", tags=["events"])
app.include_router(budget.router, prefix="/api", tags=["budget"])
app.include_router(optimize.router, prefix="/api", tags=["optimize"])
app.include_router(recovery.router, prefix="/api", tags=["recovery"])
app.include_router(presage.router, prefix="/api", tags=["presage"])
app.include_router(team.router, prefix="/api", tags=["team"])


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and load balancers."""
    return {"status": "healthy", "service": "daylight-backend"}
