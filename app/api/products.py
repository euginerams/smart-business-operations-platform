from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.product import Product
from app.models.inventory_transaction import InventoryTransaction
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate


router = APIRouter(prefix="/products", tags=["Products"])


@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    product = Product(**payload.model_dump())
    db.add(product)

    try:
        db.flush()

        # Record initial stock as an auditable opening balance.
        if product.stock_quantity > 0:
            db.add(
                InventoryTransaction(
                    product_id=product.id,
                    movement_type="stock_in",
                    quantity_change=product.stock_quantity,
                    reason="Opening stock",
                )
            )

        db.commit()
        db.refresh(product)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this SKU already exists.",
        ) from None

    return product


@router.get("/", response_model=list[ProductRead])
def list_products(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    statement = select(Product).offset(skip).limit(limit)

    if not include_inactive:
        statement = statement.where(Product.is_active.is_(True))

    return db.scalars(statement.order_by(Product.id)).all()


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    return product


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)

    if not changes:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one non-null field to update.",
        )

    for field, value in changes.items():
        setattr(product, field, value)

    try:
        db.commit()
        db.refresh(product)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The update conflicts with an existing product, possibly a duplicate SKU.",
        ) from None

    return product


@router.delete("/{product_id}", response_model=ProductRead)
def deactivate_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    product.is_active = False
    db.commit()
    db.refresh(product)

    return product
