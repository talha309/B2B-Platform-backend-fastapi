from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.database import get_db
from models.models import RFQ
from schemas import RFQUpdate, RFQResponse
from .auth_routes import admin_required

router = APIRouter(prefix="/admin", tags=["Admin"])

# Get all RFQs
@router.get("/rfqs", response_model=list[RFQResponse])
def get_rfqs(db: Session = Depends(get_db), user=Depends(admin_required)):
    return db.query(RFQ).all()

# Get single RFQ
@router.get("/rfqs/{rfq_id}", response_model=RFQResponse)
def get_rfq(rfq_id: int, db: Session = Depends(get_db), user=Depends(admin_required)):
    rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return rfq

# Update RFQ
@router.put("/rfqs/{rfq_id}", response_model=RFQResponse)
def update_rfq(rfq_id: int, rfq_update: RFQUpdate, db: Session = Depends(get_db), user=Depends(admin_required)):
    rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")

    for key, value in rfq_update.dict(exclude_unset=True).items():
        setattr(rfq, key, value)
    db.commit()
    db.refresh(rfq)
    return rfq
