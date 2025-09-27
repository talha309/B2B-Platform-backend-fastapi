from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.database import get_db
from models.models import RFQ, Quotation, RFQStatus
from schemas import QuotationCreate, QuotationResponse, RFQResponse
from utils.utils import factory_required, get_current_user
from models.models import User

router = APIRouter(prefix="/factory", tags=["factory"])

@router.get("/rfqs", response_model=list[RFQResponse])
def get_assigned_rfqs(db: Session = Depends(get_db), user: User = Depends(factory_required)):
    return db.query(RFQ).filter(RFQ.factory_id == user.id, RFQ.status == RFQStatus.approved).all()

@router.get("/rfqs/{rfq_id}", response_model=RFQResponse)
def get_rfq(rfq_id: int, db: Session = Depends(get_db), user: User = Depends(factory_required)):
    rfq = db.query(RFQ).filter(RFQ.id == rfq_id, RFQ.factory_id == user.id, RFQ.status == RFQStatus.approved).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found or not assigned")
    return rfq

@router.post("/quotations", response_model=QuotationResponse)
def create_quotation(quotation: QuotationCreate, db: Session = Depends(get_db), user: User = Depends(factory_required)):
    rfq = db.query(RFQ).filter(RFQ.id == quotation.rfq_id, RFQ.factory_id == user.id, RFQ.status == RFQStatus.approved).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found or not assigned")
    new_quotation = Quotation(
        rfq_id=quotation.rfq_id,
        factory_id=user.id,
        price=quotation.price,
        lead_time=quotation.lead_time,
        additional_info=quotation.additional_info
    )
    rfq.status = RFQStatus.quoted
    db.add(new_quotation)
    db.commit()
    db.refresh(new_quotation)
    return new_quotation