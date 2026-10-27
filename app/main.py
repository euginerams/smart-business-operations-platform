
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.customers import router as customers_router
from app.api.inventory import router as inventory_router
from app.api.products import router as products_router
from app.api.reports import router as reports_router
from app.api.sales import router as sales_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine, get_db

# Import models so SQLAlchemy registers their tables.
from app.models.customer import Customer
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.sale import Sale, SaleItem


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "A business operations platform for managing products, "
        "inventory, customers, sales, and business performance."
    ),
    version="0.6.0",
    lifespan=lifespan,
)

# Allow the deployed frontend to communicate with the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://smart-business-operations-frontend.onrender.com",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(products_router)
app.include_router(inventory_router)
app.include_router(customers_router)
app.include_router(sales_router)
app.include_router(reports_router)


@app.get("/", tags=["General"])
def root() -> dict[str, str]:
    return {
        "message": "Welcome to the Smart Business Operations Platform",
        "status": "running",
    }


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "application": settings.app_name,
    }


@app.get("/health/database", tags=["Health"])
def database_health_check(
    db: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "database": settings.db_name,
        }
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Database connection failed. "
                "Check the database configuration."
            ),
        ) from None
