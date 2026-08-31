from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from deps.auth import get_current_user
from models.db_models import User
from services.vendor_service import list_vendor_profiles, list_customer_profiles

router = APIRouter()


@router.get("/vendors")
def list_vendors(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Payable-side counterparties — who this business buys from."""
    return {"vendors": list_vendor_profiles(db, current_user.id)}


@router.get("/customers")
def list_customers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Receivable-side counterparties — who this business sells to. Same response shape as /vendors."""
    return {"vendors": list_customer_profiles(db, current_user.id)}
