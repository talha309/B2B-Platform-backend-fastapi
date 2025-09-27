from fastapi import FastAPI
from routes import auth_routes, admin_routes

app = FastAPI(title="B2B Platform")

# Routers
app.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
app.include_router(admin_routes.router, prefix="/admin", tags=["admin"])


@app.get("/")
def home():
    return {"message": "Welcome to B2B Platform"}
