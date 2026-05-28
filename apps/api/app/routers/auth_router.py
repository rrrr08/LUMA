from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.project_schema import UserCreate, UserResponse, TokenResponse, RazorpayOrderCreate, RazorpayOrderResponse, RazorpayPaymentVerify
from app.repositories.project_repo import UserRepository
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.core.config import settings
import httpx
import uuid
import hmac
import hashlib
import random
from datetime import datetime
from app.models.entities import UserInvoice

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


@router.post("/razorpay/create-order", response_model=RazorpayOrderResponse)
async def create_razorpay_order(
    payload: RazorpayOrderCreate,
    user_id: str = Depends(get_current_user_id_dependency),
    db: Session = Depends(get_db)
):
    if payload.plan not in ["pro", "startup"]:
        raise HTTPException(status_code=400, detail="Invalid plan for paid order creation")
        
    base_price = 29.0 if payload.plan == "pro" else 99.0
    if payload.promo_code and payload.promo_code.upper() == "SAVE50":
        base_price = base_price * 0.5
        
    amount_in_inr = base_price * 83
    amount_in_paise = int(amount_in_inr * 100)
    
    if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.razorpay.com/v1/orders",
                    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
                    json={
                        "amount": amount_in_paise,
                        "currency": "INR",
                        "receipt": f"receipt_{uuid.uuid4().hex[:6]}"
                    },
                    timeout=10.0
                )
            if response.status_code == 200:
                order_data = response.json()
                return RazorpayOrderResponse(
                    order_id=order_data["id"],
                    amount=order_data["amount"],
                    currency=order_data["currency"],
                    key_id=settings.RAZORPAY_KEY_ID,
                    is_mock=False
                )
            else:
                raise HTTPException(status_code=502, detail=f"Razorpay order creation failed: {response.text}")
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Razorpay integration error: {str(e)}")
    else:
        # Sandbox Mock Fallback
        mock_order_id = f"order_mock_{uuid.uuid4().hex[:12]}"
        return RazorpayOrderResponse(
            order_id=mock_order_id,
            amount=amount_in_paise,
            currency="INR",
            key_id="mock_key_id",
            is_mock=True
        )


@router.post("/razorpay/verify-payment", response_model=UserResponse)
async def verify_razorpay_payment(
    payload: RazorpayPaymentVerify,
    user_id: str = Depends(get_current_user_id_dependency),
    db: Session = Depends(get_db)
):
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    is_mock_payment = payload.razorpay_order_id.startswith("order_mock_") or not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET
    
    if not is_mock_payment:
        # Verify signature
        if not payload.razorpay_payment_id or not payload.razorpay_signature:
            raise HTTPException(status_code=400, detail="Missing razorpay_payment_id or razorpay_signature for live transaction")
            
        msg = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}"
        generated_signature = hmac.new(
            key=settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            msg=msg.encode("utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(generated_signature, payload.razorpay_signature):
            raise HTTPException(status_code=400, detail="Invalid payment signature")
            
    # Success path
    user.plan = payload.plan
    db.commit()
    db.refresh(user)
    
    # Generate Invoice
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


