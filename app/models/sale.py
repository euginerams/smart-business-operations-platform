from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Sale(Base):
    __tablename__ = "sales"

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_sale_total_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale",
        cascade="all, delete-orphan",
        order_by="SaleItem.id",
    )


class SaleItem(Base):
    __tablename__ = "sale_items"

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_item_quantity_positive"),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_sale_item_unit_price_nonnegative",
        ),
        CheckConstraint(
            "line_total >= 0",
            name="ck_sale_item_line_total_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sales.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Preserve product details as they were at the time of sale.
    product_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    sku: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    sale: Mapped["Sale"] = relationship(back_populates="items")
