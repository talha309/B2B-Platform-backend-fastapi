from sqlalchemy import Column, Integer, String, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base
import enum

class UserRole(str, enum.Enum):
    admin = "admin"
    factory = "factory"
    customer = "customer"

class RFQStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    quoted = "quoted"
    closed = "closed"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.customer, nullable=False)

    # Relationships added below

class RFQ(Base):
    __tablename__ = "rfqs"
    id = Column(Integer, primary_key=True, index=True)
    product_spec = Column(JSON, nullable=False)
    quantity = Column(Integer, nullable=False)
    destination_country = Column(String, nullable=False)
    contact_info = Column(JSON, nullable=False)
    status = Column(Enum(RFQStatus), default=RFQStatus.draft, nullable=False)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    factory_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships added below

class Quotation(Base):
    __tablename__ = "quotations"
    id = Column(Integer, primary_key=True, index=True)
    rfq_id = Column(Integer, ForeignKey("rfqs.id"), nullable=False)
    factory_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    price = Column(Integer, nullable=False)
    lead_time = Column(String, nullable=False)
    additional_info = Column(JSON, nullable=True)

    # Relationships added below

# Define relationships after classes to avoid order issues
User.rfqs = relationship("RFQ", back_populates="customer", foreign_keys=["RFQ.customer_id"])
User.assigned_rfqs = relationship("RFQ", back_populates="factory", foreign_keys=["RFQ.factory_id"])
User.quotations = relationship("Quotation", back_populates="factory")

RFQ.customer = relationship("User", foreign_keys=[RFQ.customer_id], back_populates="rfqs")
RFQ.factory = relationship("User", foreign_keys=[RFQ.factory_id], back_populates="assigned_rfqs")
RFQ.quotations = relationship("Quotation", back_populates="rfq")

Quotation.rfq = relationship("RFQ", back_populates="quotations")
Quotation.factory = relationship("User", back_populates="quotations")