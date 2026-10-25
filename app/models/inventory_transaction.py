from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    __table_args__ = (
        CheckConstraint(
            "quantity_change != 0",
            name="ck_inventory_transaction_nonzero_quantity",
        ),
        CheckConstraint(
            "movement_type IN ('stock_in', 'stock_out', 'adjustment')",
            name="ck_inventory_transaction_movement_type",
        ),
        CheckConstraint(
            "(movement_type != 'stock_in' OR quantity_change > 0)",
            name="ck_inventory_transaction_stock_in_positive",
        ),
        CheckConstraint(
            "(movement_type != 'stock_out' OR quantity_change < 0)",
            name="ck_inventory_transaction_stock_out_negative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    movement_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Positive values add stock; negative values remove stock.
    quantity_change: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
