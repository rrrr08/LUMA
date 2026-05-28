from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.repositories.project_repo import RequestLogRepository
from app.routers.auth_router import get_current_user_id_dependency as get_current_user_id

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/summary")
def get_analytics_summary(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    repo = RequestLogRepository(db)
    return repo.get_summary_by_user(user_id)

@router.get("/per-endpoint")
def get_per_endpoint_stats(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    repo = RequestLogRepository(db)
    return repo.get_per_endpoint(user_id)
