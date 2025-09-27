from fastapi import FastAPI
from database.database import Base, engine
from routes import auth_routes, admin_routes, customer_routes, factory_routes

app = FastAPI()

# Create tables if they don’t exist
Base.metadata.create_all(bind=engine)

app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(customer_routes.router)
app.include_router(factory_routes.router)

@app.get("/")
def home():
    return {"msg": "Welcome to B2B Platform"}