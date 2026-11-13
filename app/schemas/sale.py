from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SaleItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class SaleCreate(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    items: list[SaleItemCreate] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_unique_products(self):
        product_ids = [item.product_id for item in self.items]

        if len(product_ids) != len(set(product_ids)):
            raise ValueError(
                "Each product may appear only once per sale. "
                "Combine quantities for duplicate products."
            )

        return self


class SaleItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    sku: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class SaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int | None
    total_amount: Decimal
    created_at: datetime
    items: list[SaleItemRead]
