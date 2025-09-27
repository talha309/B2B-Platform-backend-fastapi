from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.database import get_db
from models.models import RFQ, User, RFQStatus
from schemas import RFQResponse, RFQUpdate
from utils.utils import admin_required

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/rfqs", response_model=list[RFQResponse])
def get_rfqs(db: Session = Depends(get_db), user=Depends(admin_required)):
    return db.query(RFQ).all()

@router.get("/rfqs/{rfq_id}", response_model=RFQResponse)
def get_rfq(rfq_id: int, db: Session = Depends(get_db), user=Depends(admin_required)):
    rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return rfq

@router.put("/rfqs/{rfq_id}", response_model=RFQResponse)
def update_rfq(rfq_id: int, rfq_update: RFQUpdate, db: Session = Depends(get_db), user=Depends(admin_required)):
    rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")
    if rfq_update.factory_id:
        factory = db.query(User).filter(User.id == rfq_update.factory_id, User.role == "factory").first()
        if not factory:
            raise HTTPException(status_code=400, detail="Invalid factory ID")
    if rfq_update.status and rfq_update.status == RFQStatus.approved and not rfq_update.factory_id:
        raise HTTPException(status_code=400, detail="Factory ID required to approve RFQ")
    for key, value in rfq_update.dict(exclude_unset=True).items():
        setattr(rfq, key, value)
    db.commit()
    db.refresh(rfq)
    return rfq