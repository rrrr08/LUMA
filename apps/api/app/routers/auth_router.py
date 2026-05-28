from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.project_schema import UserCreate, UserResponse, TokenResponse
from app.repositories.project_repo import UserRepository
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Use auto_error=False to let us handle missing tokens customly
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)

@router.post("/register", response_model=TokenResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    existing_user = user_repo.get_by_email(user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered."
        )
    hashed_pwd = hash_password(user_in.password)
    user = user_repo.create(email=user_in.email, hashed_password=hashed_pwd)
    access_token = create_access_token(subject=user.id)
    return TokenResponse(access_token=access_token)

@router.post("/login", response_model=TokenResponse)
def login(credentials: UserCreate, db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(credentials.email)
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )
    access_token = create_access_token(subject=user.id)
    return TokenResponse(access_token=access_token)

def get_current_user_id_dependency(
    token: str = Depends(oauth2_scheme)
) -> str:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return user_id

@router.get("/me", response_model=UserResponse)
def get_me(user_id: str = Depends(get_current_user_id_dependency), db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse(id=user.id, email=user.email, role=user.role, plan=user.plan or "free")

from typing import List, Optional
from pydantic import BaseModel

class PlanUpdateRequest(BaseModel):
    plan: str
    promo_code: Optional[str] = None

@router.put("/plan", response_model=UserResponse)
def update_user_plan(
    payload: PlanUpdateRequest,
    user_id: str = Depends(get_current_user_id_dependency),
    db: Session = Depends(get_db)
):
    if payload.plan not in ["free", "pro", "startup"]:
        raise HTTPException(status_code=400, detail="Invalid plan selected")
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_plan = user.plan
    user.plan = payload.plan
    db.commit()
    db.refresh(user)

    # Generate an invoice record if user is upgrading/changing plan to paid tier
    if payload.plan in ["pro", "startup"] and old_plan != payload.plan:
        import random
        from datetime import datetime
        from app.models.entities import UserInvoice

        base_price = 29.0 if payload.plan == "pro" else 99.0
        if payload.promo_code and payload.promo_code.upper() == "SAVE50":
            base_price = base_price * 0.5

        inv_num = f"INV-{datetime.now().year}-{random.randint(1000, 9999)}"
        invoice = UserInvoice(
            user_id=user.id,
            invoice_number=inv_num,
            plan=payload.plan,
            amount=base_price,
            status="paid"
        )
        db.add(invoice)
        db.commit()

    return UserResponse(id=user.id, email=user.email, role=user.role, plan=user.plan or "free")


from app.schemas.project_schema import InvoiceResponse, QuotaSettingsResponse, QuotaSettingsUpdate
from app.models.entities import UserInvoice, UserQuotaSettings

@router.get("/invoices", response_model=List[InvoiceResponse])
def get_user_invoices(
    user_id: str = Depends(get_current_user_id_dependency),
    db: Session = Depends(get_db)
):
    invoices = db.query(UserInvoice).filter(UserInvoice.user_id == user_id).order_by(UserInvoice.billing_date.desc()).all()
    return invoices


@router.get("/quota-settings", response_model=QuotaSettingsResponse)
def get_quota_settings(
    user_id: str = Depends(get_current_user_id_dependency),
    db: Session = Depends(get_db)
):
    q_settings = db.query(UserQuotaSettings).filter(UserQuotaSettings.user_id == user_id).first()
    if not q_settings:
        q_settings = UserQuotaSettings(
            user_id=user_id,
            email_alerts_enabled=True,
            slack_alerts_enabled=False,
            threshold_percentage=80
        )
        db.add(q_settings)
        db.commit()
        db.refresh(q_settings)
    return q_settings


@router.put("/quota-settings", response_model=QuotaSettingsResponse)
def update_quota_settings(
    payload: QuotaSettingsUpdate,
    user_id: str = Depends(get_current_user_id_dependency),
    db: Session = Depends(get_db)
):
    q_settings = db.query(UserQuotaSettings).filter(UserQuotaSettings.user_id == user_id).first()
    if not q_settings:
        q_settings = UserQuotaSettings(user_id=user_id)
        db.add(q_settings)
    
    q_settings.email_alerts_enabled = payload.email_alerts_enabled
    q_settings.slack_alerts_enabled = payload.slack_alerts_enabled
    q_settings.slack_webhook_url = payload.slack_webhook_url
    q_settings.threshold_percentage = payload.threshold_percentage
    
    db.commit()
    db.refresh(q_settings)
    return q_settings

