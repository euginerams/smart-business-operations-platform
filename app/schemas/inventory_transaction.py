from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


MovementType = Literal["stock_in", "stock_out", "adjustment"]
AdjustmentDirection = Literal["increase", "decrease"]


class InventoryTransactionCreate(BaseModel):
    product_id: int = Field(gt=0)
    movement_type: MovementType
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=255)
    adjustment_direction: AdjustmentDirection | None = None

    @model_validator(mode="after")
    def validate_adjustment_direction(self):
        if self.movement_type == "adjustment":
            if self.adjustment_direction is None:
                raise ValueError(
                    "Adjustment transactions require an adjustment_direction."
                )
        elif self.adjustment_direction is not None:
            raise ValueError(
                "adjustment_direction is only valid for adjustment transactions."
            )

        return self


class InventoryTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    movement_type: MovementType
    quantity_change: int
    reason: str
    created_at: datetime
