from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Dict
from enum import Enum

class UserRole(str, Enum):
    admin = "admin"
    factory = "factory"
    customer = "customer"

class RFQStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    quoted = "quoted"
    closed = "closed"

class UserBase(BaseModel):
    email: EmailStr
    role: UserRole

class UserCreate(UserBase):
    password: str

    @validator("password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RFQBase(BaseModel):
    product_spec: Dict
    quantity: int
    destination_country: str
    contact_info: Dict

    @validator("quantity")
    def quantity_positive(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v

    @validator("destination_country")
    def valid_country(cls, v):
        # Simplified validation; could use a country code library
        if not v.isalpha() or len(v) < 2:
            raise ValueError("Invalid destination country")
        return v.upper()

class RFQCreate(RFQBase):
    pass

class RFQUpdate(BaseModel):
    product_spec: Optional[Dict] = None
    quantity: Optional[int] = None
    destination_country: Optional[str] = None
    contact_info: Optional[Dict] = None
    status: Optional[RFQStatus] = None
    factory_id: Optional[int] = None

class RFQResponse(RFQBase):
    id: int
    status: RFQStatus
    customer_id: int
    factory_id: Optional[int]

    class Config:
        from_attributes = True

class QuotationBase(BaseModel):
    price: int
    lead_time: str
    additional_info: Optional[Dict] = None

    @validator("price")
    def price_positive(cls, v):
        if v <= 0:
            raise ValueError("Price must be positive")
        return v

class QuotationCreate(QuotationBase):
    rfq_id: int

class QuotationResponse(QuotationBase):
    id: int
    rfq_id: int
    factory_id: int

    class Config:
        from_attributes = True