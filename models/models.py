from sqlalchemy import Column, String, Integer, Boolean, Enum, JSON, ForeignKey
from sqlalchemy.orm import relationship 
from database.database import Base
import enum

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.customer, nullable=False)

class RFQ(Base):
    __tablename__ = "rfqs"
    id = Column(Integer, primary_key=True, index=True)
    product_spec = Column(JSON, nullable=False)
    quantity = Column(Integer, nullable=False)
    destination_country = Column(String, nullable=False)
    contact_info = Column(JSON, nullable=False)
    status = Column(String, default="draft")