from fastapi import FastAPI
from routes import auth_routes, admin_routes
from database.database import Base, engine

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="B2B Platform")

# Routers
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)

@app.get("/")
def home():
    return {"message": "Welcome to B2B Platform"}
