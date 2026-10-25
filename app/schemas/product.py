from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    sku: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    stock_quantity: int = Field(default=0, ge=0)
    is_active: bool = True


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str | None = Field(default=None, min_length=2, max_length=50)
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    is_active: bool | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    description: str | None
    category: str | None
    price: Decimal
    stock_quantity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
