from pydantic import BaseModel, EmailStr
from typing import Optional, Dict

# User
class UserBase(BaseModel):
    email: EmailStr
    role: str  # "admin", "factory", "customer"

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    class Config:
        orm_mode = True

# Auth
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# RFQ
class RFQBase(BaseModel):
    product_spec: Dict
    quantity: int
    destination_country: str
    contact_info: Dict

class RFQUpdate(BaseModel):
    product_spec: Optional[Dict] = None
    quantity: Optional[int] = None
    destination_country: Optional[str] = None
    contact_info: Optional[Dict] = None
    status: Optional[str] = None

class RFQResponse(RFQBase):
    id: int
    status: str
    class Config:
        orm_mode = True
