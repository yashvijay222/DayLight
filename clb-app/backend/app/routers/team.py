from fastapi import APIRouter, Request

from app.models import TeamMetrics

router = APIRouter()


@router.get("/team/health-score", response_model=TeamMetrics)
def get_team_metrics(request: Request) -> TeamMetrics:
    return request.app.state.team_metrics
