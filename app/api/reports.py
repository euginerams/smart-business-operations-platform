from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.customer import Customer
from app.models.product import Product
from app.models.sale import Sale, SaleItem


router = APIRouter(prefix="/reports", tags=["Reports"])


def get_date_filters(start_date: date | None, end_date: date | None):
    """Build inclusive date filters for sales reports."""

    if start_date is not None and end_date is not None:
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date cannot be later than end_date.",
            )

    filters = []

    if start_date is not None:
        filters.append(
            Sale.created_at >= datetime.combine(start_date, time.min)
        )

    if end_date is not None:
        filters.append(
            Sale.created_at
            < datetime.combine(end_date + timedelta(days=1), time.min)
        )

    return filters


@router.get("/summary")
def get_business_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    """Return sales performance and current business totals."""

    filters = get_date_filters(start_date, end_date)

    total_sales = db.scalar(
        select(func.count(Sale.id)).where(*filters)
    ) or 0

    total_revenue = db.scalar(
        select(func.coalesce(func.sum(Sale.total_amount), 0)).where(
            *filters
        )
    ) or Decimal("0.00")

    units_sold = db.scalar(
        select(func.coalesce(func.sum(SaleItem.quantity), 0))
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(*filters)
    ) or 0

    active_products = db.scalar(
        select(func.count(Product.id)).where(
            Product.is_active.is_(True)
        )
    ) or 0

    active_customers = db.scalar(
        select(func.count(Customer.id)).where(
            Customer.is_active.is_(True)
        )
    ) or 0

    inventory_value = db.scalar(
        select(
            func.coalesce(
                func.sum(Product.price * Product.stock_quantity),
                0,
            )
        ).where(Product.is_active.is_(True))
    ) or Decimal("0.00")

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "units_sold": units_sold,
        "active_products": active_products,
        "active_customers": active_customers,
        "inventory_value": inventory_value,
    }


@router.get("/top-products")
def get_top_products(
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Rank products by the total number of units sold."""

    filters = get_date_filters(start_date, end_date)

    statement = (
        select(
            SaleItem.product_id.label("product_id"),
            SaleItem.product_name.label("product_name"),
            SaleItem.sku.label("sku"),
            func.sum(SaleItem.quantity).label("units_sold"),
            func.sum(SaleItem.line_total).label("revenue"),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(*filters)
        .group_by(
            SaleItem.product_id,
            SaleItem.product_name,
            SaleItem.sku,
        )
        .order_by(
            func.sum(SaleItem.quantity).desc(),
            func.sum(SaleItem.line_total).desc(),
        )
        .limit(limit)
    )

    results = db.execute(statement).all()

    return [
        {
            "product_id": row.product_id,
            "product_name": row.product_name,
            "sku": row.sku,
            "units_sold": row.units_sold,
            "revenue": row.revenue,
        }
        for row in results
    ]


@router.get("/low-stock")
def get_low_stock_products(
    threshold: int = Query(default=5, ge=0),
    db: Session = Depends(get_db),
):
    """List active products whose stock is at or below the threshold."""

    statement = (
        select(Product)
        .where(
            Product.is_active.is_(True),
            Product.stock_quantity <= threshold,
        )
        .order_by(Product.stock_quantity.asc(), Product.name.asc())
    )

    products = db.scalars(statement).all()

    return [
        {
            "product_id": product.id,
            "sku": product.sku,
            "name": product.name,
            "category": product.category,
            "stock_quantity": product.stock_quantity,
            "unit_price": product.price,
            "inventory_value": (
                Decimal(str(product.price))
                * product.stock_quantity
            ),
        }
        for product in products
    ]


@router.get("/inventory-health")
def get_inventory_health(
    threshold: int = Query(default=5, ge=0),
    db: Session = Depends(get_db),
):
    """Summarise stock quantities and product counts by stock health."""

    low_stock_condition = Product.stock_quantity <= threshold
    healthy_stock_condition = Product.stock_quantity > threshold

    statement = select(
        func.count(Product.id).label("active_products"),
        func.coalesce(
            func.sum(Product.stock_quantity), 0
        ).label("total_stock_units"),
        func.coalesce(
            func.sum(
                case(
                    (low_stock_condition, Product.stock_quantity),
                    else_=0,
                )
            ),
            0,
        ).label("low_stock_units"),
        func.coalesce(
            func.sum(
                case(
                    (healthy_stock_condition, Product.stock_quantity),
                    else_=0,
                )
            ),
            0,
        ).label("healthy_stock_units"),
        func.coalesce(
            func.sum(case((low_stock_condition, 1), else_=0)),
            0,
        ).label("low_stock_products"),
        func.coalesce(
            func.sum(case((healthy_stock_condition, 1), else_=0)),
            0,
        ).label("healthy_stock_products"),
        func.coalesce(
            func.sum(Product.price * Product.stock_quantity), 0
        ).label("inventory_value"),
    ).where(Product.is_active.is_(True))

    result = db.execute(statement).one()

    return {
        "threshold": threshold,
        "active_products": result.active_products,
        "total_stock_units": result.total_stock_units,
        "low_stock_units": result.low_stock_units,
        "healthy_stock_units": result.healthy_stock_units,
        "low_stock_products": result.low_stock_products,
        "healthy_stock_products": result.healthy_stock_products,
        "inventory_value": result.inventory_value,
    }