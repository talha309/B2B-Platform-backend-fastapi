# app/main.py
# Updated FastAPI application with user signup/login, database-backed users, and existing RFQ features.
# Authentication: JWT with OAuth2, passwords hashed with bcrypt.
# Database: PostgreSQL with SQLAlchemy, new User model.
# Email: Sends welcome email on signup using Gmail SMTP (as configured).
# Dependencies: pip install fastapi sqlalchemy psycopg2-binary pydantic uvicorn python-dotenv python-jose[cryptography] passlib[bcrypt==4.0.1] aiosmtplib
# Run: uvicorn main:app --reload

import os
from datetime import datetime, timedelta
from typing import List, Optional, Annotated
from fastapi import FastAPI, Depends, HTTPException, Query, Body, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from passlib.context import CryptContext
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import os.path

load_dotenv()

# Security setup
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")  # Change in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/dbname")
# pool_pre_ping helps avoid stale connections in some environments
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

class RFQ(Base):
    __tablename__ = "rfqs"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    country = Column(String)
    product_category = Column(String)
    fields = Column(Text)
    conversation_transcript = Column(Text)
    attachments = Column(ARRAY(String))
    activities = relationship("ActivityLog", back_populates="rfq")

class Factory(Base):
    __tablename__ = "factories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String)  # Added for email sending
    capabilities = Column(ARRAY(String))
    location = Column(String)
    lead_time = Column(Integer)
    certifications = Column(ARRAY(String))
    price_band = Column(String)

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(Text)
    rfq_id = Column(Integer, ForeignKey("rfqs.id"))
    rfq = relationship("RFQ", back_populates="activities")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    factory_id = Column(Integer, ForeignKey("factories.id"))

Base.metadata.create_all(bind=engine)

# Pydantic models
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: int
    is_active: bool

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class RFQBase(BaseModel):
    status: str
    country: str
    product_category: str
    fields: str
    conversation_transcript: Optional[str] = None
    attachments: Optional[List[str]] = None

class RFQCreate(RFQBase):
    pass

class RFQUpdate(BaseModel):
    status: Optional[str] = None
    country: Optional[str] = None
    product_category: Optional[str] = None
    fields: Optional[str] = None
    conversation_transcript: Optional[str] = None
    attachments: Optional[List[str]] = None

class RFQOut(RFQBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class FactoryBase(BaseModel):
    name: str
    email: str
    capabilities: List[str]
    location: str
    lead_time: int
    certifications: List[str]
    price_band: str

class FactoryCreate(FactoryBase):
    pass

class FactoryOut(FactoryBase):
    id: int

    class Config:
        orm_mode = True

class ActivityLogOut(BaseModel):
    id: int
    action: str
    timestamp: datetime
    details: str

    class Config:
        orm_mode = True

class Analytics(BaseModel):
    inquiries_per_month: int
    conversion_rate: float
    average_response_time: float
    demand_heatmap: dict

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication logic
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return False
    if not user.is_active:
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    # Ensure 'sub' is present if caller didn't include it
    if "sub" not in to_encode and "username" in to_encode:
        to_encode["sub"] = to_encode["username"]
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

app = FastAPI()

# Exception handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )

# Email functions
async def send_email_welcome(email: str, username: str):
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        sender = os.getenv("SENDER_EMAIL")
        password = os.getenv("SENDER_PASSWORD")

        msg = MIMEMultipart()
        msg['Subject'] = "Welcome to B2B Platform"
        msg['From'] = sender
        msg['To'] = email
        msg.attach(MIMEText(f"Hello {username},\n\nWelcome to the B2B Platform! Your account is active.\n\nRegards,\nB2B Platform Team", "plain"))

        # aiosmtplib prefers a Message object and start_tls=True for port 587
        await aiosmtplib.send(
            msg,
            hostname=smtp_server,
            port=smtp_port,
            username=sender,
            password=password,
            start_tls=True
        )
    except Exception as e:
        # Do not raise: signing up should succeed even if email fails
        print(f"Welcome email failed: {str(e)}")

async def send_email(factory: Factory, rfq: RFQ):
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        sender = os.getenv("SENDER_EMAIL")
        password = os.getenv("SENDER_PASSWORD")

        msg = MIMEMultipart()
        msg['Subject'] = "New RFQ Request"
        msg['From'] = sender
        msg['To'] = factory.email or ""
        body_text = f"New RFQ: {rfq.fields}\n\nTranscript:\n{rfq.conversation_transcript or 'N/A'}"
        msg.attach(MIMEText(body_text, "plain"))

        # Attach files safely (if attachments are filesystem paths)
        for attachment in rfq.attachments or []:
            try:
                if not attachment:
                    continue
                filename = os.path.basename(attachment)
                with open(attachment, "rb") as f:
                    part = MIMEApplication(f.read(), Name=filename)
                    part['Content-Disposition'] = f'attachment; filename="{filename}"'
                    msg.attach(part)
            except FileNotFoundError:
                # skip missing attachments but log
                print(f"Attachment not found: {attachment}")
            except Exception as ex:
                print(f"Failed to attach {attachment}: {ex}")

        await aiosmtplib.send(
            msg,
            hostname=smtp_server,
            port=smtp_port,
            username=sender,
            password=password,
            start_tls=True
        )
    except Exception as e:
        print(f"RFQ email failed: {str(e)}")

# Placeholder webhook
def send_webhook(factory: Factory, rfq: RFQ):
    print(f"Sending webhook to factory {factory.id} for RFQ {rfq.id}")

# Log activity
def log_activity(db: Session, rfq_id: int, action: str, details: str):
    try:
        log = ActivityLog(action=action, details=details, rfq_id=rfq_id)
        db.add(log)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Logging failed: {str(e)}")

# Signup endpoint
@app.post("/signup", response_model=UserOut)
async def signup(user: UserCreate, db: Session = Depends(get_db)):
    try:
        # Check if username or email exists
        if db.query(User).filter(User.username == user.username).first():
            raise HTTPException(status_code=400, detail="Username already registered")
        if db.query(User).filter(User.email == user.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        # Hash password
        hashed_password = pwd_context.hash(user.password)
        db_user = User(
            username=user.username,
            email=user.email,
            hashed_password=hashed_password,
            is_active=True
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        # Send welcome email (fire-and-forget style)
        await send_email_welcome(user.email, user.username)
        return db_user
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Login endpoint
@app.post("/login", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# RFQ List with Filters
@app.get("/rfqs", response_model=List[RFQOut])
def get_rfqs(
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    country: Optional[str] = Query(None),
    product_category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        query = db.query(RFQ)
        if status:
            query = query.filter(RFQ.status == status)
        if start_date:
            query = query.filter(RFQ.created_at >= start_date)
        if end_date:
            query = query.filter(RFQ.created_at <= end_date)
        if country:
            query = query.filter(RFQ.country == country)
        if product_category:
            query = query.filter(RFQ.product_category == product_category)
        return query.all()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# RFQ Detail View
@app.get("/rfqs/{rfq_id}", response_model=RFQOut)
def get_rfq_detail(
    rfq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")
        return rfq
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Suggested Factories
@app.get("/rfqs/{rfq_id}/suggested_factories", response_model=List[FactoryOut])
def get_suggested_factories(
    rfq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")
        factories = db.query(Factory).filter(
            Factory.location == rfq.country,
            Factory.capabilities.contains([rfq.product_category])
        ).all()
        return factories
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Edit RFQ
@app.put("/rfqs/{rfq_id}")
def update_rfq(
    rfq_id: int,
    rfq_update: RFQUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")
        update_data = rfq_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(rfq, key, value)
        db.commit()
        db.refresh(rfq)
        log_activity(db, rfq_id, "RFQ Updated", str(update_data))
        return {"message": "RFQ updated"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Factory Search
@app.get("/factories", response_model=List[FactoryOut])
def search_factories(
    capabilities: Optional[str] = Query(None),
    lead_time_max: Optional[int] = Query(None),
    certifications: Optional[str] = Query(None),
    price_band: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        query = db.query(Factory)
        if capabilities:
            caps = capabilities.split(",")
            for cap in caps:
                query = query.filter(Factory.capabilities.contains([cap.strip()]))
        if lead_time_max is not None:
            query = query.filter(Factory.lead_time <= lead_time_max)
        if certifications:
            certs = certifications.split(",")
            for cert in certs:
                query = query.filter(Factory.certifications.contains([cert.strip()]))
        if price_band:
            query = query.filter(Factory.price_band == price_band)
        return query.all()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Forward RFQ
@app.post("/rfqs/{rfq_id}/forward")
async def forward_rfq(
    rfq_id: int,
    factory_ids: List[int] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")
        if rfq.status != "approved":
            raise HTTPException(status_code=400, detail="RFQ must be approved first")

        for factory_id in factory_ids:
            factory = db.query(Factory).filter(Factory.id == factory_id).first()
            if not factory:
                continue
            await send_email(factory, rfq)
            send_webhook(factory, rfq)
            notification = Notification(message=f"New RFQ: {rfq_id}", factory_id=factory_id)
            db.add(notification)

        db.commit()
        rfq.status = "forwarded"
        db.commit()
        log_activity(db, rfq_id, "RFQ Forwarded", f"To factories: {factory_ids}")
        return {"message": "RFQ forwarded"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# Activity Log
@app.get("/rfqs/{rfq_id}/activity_log", response_model=List[ActivityLogOut])
def get_activity_log(
    rfq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        logs = db.query(ActivityLog).filter(ActivityLog.rfq_id == rfq_id).all()
        return logs
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Analytics
@app.get("/analytics", response_model=Analytics)
def get_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        inquiries_per_month = db.query(func.count(RFQ.id)).filter(RFQ.created_at >= current_month_start).scalar() or 0
        total = db.query(func.count(RFQ.id)).scalar() or 0
        forwarded = db.query(func.count(RFQ.id)).filter(RFQ.status == "forwarded").scalar() or 0
        conversion_rate = (forwarded / total) * 100 if total > 0 else 0.0

        # average response time: try to compute in Python if DB returns interval-like objects
        avg_response_subq = db.query(func.avg(ActivityLog.timestamp - RFQ.created_at)).join(RFQ).filter(ActivityLog.action == "RFQ Forwarded").scalar()
        if avg_response_subq is None:
            average_response_time = 0.0
        else:
            # avg_response_subq might be a timedelta-like or numeric depending on DB drivers
            try:
                total_seconds = avg_response_subq.total_seconds()
            except AttributeError:
                # numeric seconds in some setups
                total_seconds = float(avg_response_subq)
            average_response_time = total_seconds / 3600.0  # hours

        heatmap_query = db.query(
            RFQ.product_category,
            RFQ.country,
            func.count(RFQ.id)
        ).group_by(RFQ.product_category, RFQ.country).all()
        demand_heatmap = {}
        for cat, country, count in heatmap_query:
            if cat not in demand_heatmap:
                demand_heatmap[cat] = {}
            demand_heatmap[cat][country] = count
        return Analytics(
            inquiries_per_month=inquiries_per_month,
            conversion_rate=conversion_rate,
            average_response_time=average_response_time,
            demand_heatmap=demand_heatmap
        )
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Create RFQ
@app.post("/rfqs", response_model=RFQOut)
def create_rfq(
    rfq: RFQCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        db_rfq = RFQ(**rfq.dict())
        db.add(db_rfq)
        db.commit()
        db.refresh(db_rfq)
        log_activity(db, db_rfq.id, "RFQ Created", "")
        return db_rfq
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Create Factory
@app.post("/factories", response_model=FactoryOut)
def create_factory(
    factory: FactoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        db_factory = Factory(**factory.dict())
        db.add(db_factory)
        db.commit()
        db.refresh(db_factory)
        return db_factory
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Approve RFQ
@app.post("/rfqs/{rfq_id}/approve")
def approve_rfq(
    rfq_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        rfq = db.query(RFQ).filter(RFQ.id == rfq_id).first()
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")
        rfq.status = "approved"
        db.commit()
        log_activity(db, rfq_id, "RFQ Approved", "")
        return {"message": "RFQ approved"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
from typing import List
from fastapi import Form

@app.post("/send-test-email")
async def send_test_email(
    recipients: List[str] = Form(..., description="List of recipient emails (comma separated)"),
    subject: str = Form("Test Email from FastAPI"),
    body: str = Form("This is a test email."),
):
    try:
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        sender = os.getenv("SENDER_EMAIL")
        password = os.getenv("SENDER_PASSWORD")

        # Ensure recipients is a proper list
        if isinstance(recipients, str):
            recipients = [r.strip() for r in recipients.split(",")]

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(body, "plain"))

        # ✅ Use starttls with port 587
        await aiosmtplib.send(
            msg.as_string(),
            recipients=recipients,
            sender=sender,
            hostname=smtp_server,
            port=smtp_port,
            username=sender,
            password=password,
            start_tls=True
        )

        return {"message": f"✅ Email sent to {', '.join(recipients)}"}
    except Exception as e:
        return {"error": str(e)}
