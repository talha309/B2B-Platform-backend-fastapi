from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.database import get_db
from models.models import RFQ, RFQStatus
from schemas import RFQCreate, RFQResponse
from utils.utils import customer_required, get_current_user
from models.models import User

router = APIRouter(prefix="/customer", tags=["customer"])

@router.post("/rfqs", response_model=RFQResponse)
def create_rfq(rfq: RFQCreate, db: Session = Depends(get_db), user: User = Depends(customer_required)):
    new_rfq = RFQ(
        product_spec=rfq.product_spec,
        quantity=rfq.quantity,
        destination_country=rfq.destination_country,
        contact_info=rfq.contact_info,
        status=RFQStatus.draft,
        customer_id=user.id
    )
    db.add(new_rfq)
    db.commit()
    db.refresh(new_rfq)
    return new_rfq

@router.get("/rfqs", response_model=list[RFQResponse])
def get_my_rfqs(db: Session = Depends(get_db), user: User = Depends(customer_required)):
    return db.query(RFQ).filter(RFQ.customer_id == user.id).all()

@router.get("/rfqs/{rfq_id}", response_model=RFQResponse)
def get_rfq(rfq_id: int, db: Session = Depends(get_db), user: User = Depends(customer_required)):
    rfq = db.query(RFQ).filter(RFQ.id == rfq_id, RFQ.customer_id == user.id).first()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found or not authorized")
    return rfq