
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.schemas.inventory_transaction import (
    InventoryTransactionCreate,
    InventoryTransactionRead,
)


router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.post(
    "/transactions",
    response_model=InventoryTransactionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory_transaction(
    payload: InventoryTransactionCreate,
    db: Session = Depends(get_db),
):
    # Lock the product row while calculating and recording its stock movement.
    statement = (
        select(Product)
        .where(Product.id == payload.product_id)
        .with_for_update()
    )
    product = db.scalar(statement)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    if not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot change inventory for an inactive product.",
        )

    if payload.movement_type == "stock_in":
        quantity_change = payload.quantity

    elif payload.movement_type == "stock_out":
        quantity_change = -payload.quantity

    elif payload.movement_type == "adjustment":
        if payload.adjustment_direction == "increase":
            quantity_change = payload.quantity
        else:
            quantity_change = -payload.quantity

    else:
        # The schema should reject unsupported movement types.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported inventory movement type.",
        )

    new_stock = product.stock_quantity + quantity_change

    if new_stock < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Insufficient stock. Available: {product.stock_quantity}; "
                f"requested: {payload.quantity}."
            ),
        )

    transaction = InventoryTransaction(
        product_id=product.id,
        movement_type=payload.movement_type,
        quantity_change=quantity_change,
        reason=payload.reason.strip(),
    )

    product.stock_quantity = new_stock
    db.add(transaction)

    try:
        db.commit()
        db.refresh(transaction)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The inventory transaction conflicts with a database constraint.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The inventory transaction could not be saved.",
        ) from None

    return transaction


@router.get(
    "/products/{product_id}/transactions",
    response_model=list[InventoryTransactionRead],
)
def list_product_transactions(
    product_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    statement = (
        select(InventoryTransaction)
        .where(InventoryTransaction.product_id == product_id)
        .order_by(
            InventoryTransaction.created_at.desc(),
            InventoryTransaction.id.desc(),
        )
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(statement).all()
