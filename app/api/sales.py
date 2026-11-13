from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.customer import Customer
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.schemas.sale import SaleCreate, SaleRead


router = APIRouter(prefix="/sales", tags=["Sales"])


@router.post("/", response_model=SaleRead, status_code=status.HTTP_201_CREATED)
def create_sale(payload: SaleCreate, db: Session = Depends(get_db)):
    """Create a sale, deduct stock, and record stock movements atomically."""

    # Validate the customer before changing anything.
    if payload.customer_id is not None:
        customer = db.scalar(
            select(Customer).where(Customer.id == payload.customer_id)
        )

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found.",
            )

        if not customer.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create a sale for an inactive customer.",
            )

    product_ids = sorted(item.product_id for item in payload.items)

    # Lock product rows in a consistent order to reduce deadlock risk
    # when multiple sales are being processed concurrently in PostgreSQL.
    products = db.scalars(
        select(Product)
        .where(Product.id.in_(product_ids))
        .order_by(Product.id)
        .with_for_update()
    ).all()

    products_by_id = {product.id: product for product in products}

    missing_ids = [
        product_id
        for product_id in product_ids
        if product_id not in products_by_id
    ]

    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product(s) not found: {missing_ids}",
        )

    # Validate every product and quantity before changing stock.
    for item in payload.items:
        product = products_by_id[item.product_id]

        if not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{product.name}' is inactive.",
            )

        if product.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock_quantity}; "
                    f"requested: {item.quantity}."
                ),
            )

    # Use decimal arithmetic for currency calculations.
    total_amount = Decimal("0.00")
    prepared_items = []

    for item in payload.items:
        product = products_by_id[item.product_id]
        unit_price = Decimal(str(product.price)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        line_total = (unit_price * item.quantity).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        prepared_items.append(
            {
                "product": product,
                "quantity": item.quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )
        total_amount += line_total

    total_amount = total_amount.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    try:
        sale = Sale(
            customer_id=payload.customer_id,
            total_amount=total_amount,
        )
        db.add(sale)

        # Obtain the sale ID before creating its related records.
        db.flush()

        for item_data in prepared_items:
            product = item_data["product"]
            quantity = item_data["quantity"]

            sale.items.append(
                SaleItem(
                    product_id=product.id,
                    product_name=product.name,
                    sku=product.sku,
                    quantity=quantity,
                    unit_price=item_data["unit_price"],
                    line_total=item_data["line_total"],
                )
            )

            product.stock_quantity -= quantity

            db.add(
                InventoryTransaction(
                    product_id=product.id,
                    movement_type="stock_out",
                    quantity_change=-quantity,
                    reason=f"Sale #{sale.id}",
                )
            )

        # The sale, sale items, stock changes, and transactions
        # are committed together.
        db.commit()
        db.refresh(sale)

        return sale

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The sale could not be saved because of a data conflict.",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while processing the sale.",
        ) from exc


@router.get("/", response_model=list[SaleRead])
def list_sales(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List recent sales, including their line items."""

    statement = (
        select(Sale)
        .options(selectinload(Sale.items))
        .order_by(Sale.created_at.desc(), Sale.id.desc())
        .offset(skip)
        .limit(limit)
    )

    return db.scalars(statement).all()


@router.get("/{sale_id}", response_model=SaleRead)
def get_sale(sale_id: int, db: Session = Depends(get_db)):
    """Retrieve one sale and its line items."""

    statement = (
        select(Sale)
        .options(selectinload(Sale.items))
        .where(Sale.id == sale_id)
    )

    sale = db.scalar(statement)

    if sale is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sale not found.",
        )

    return sale
