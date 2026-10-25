from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Import models so every table is registered with SQLAlchemy.
from app.models.customer import Customer
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.sale import Sale, SaleItem


@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def create_product(client, **overrides):
    product = {
        "sku": "REPORT-001",
        "name": "Business Laptop",
        "description": "Laptop for business reporting tests",
        "category": "Computers",
        "price": "25.00",
        "stock_quantity": 10,
        "is_active": True,
    }
    product.update(overrides)

    response = client.post("/products/", json=product)
    assert response.status_code == 201, response.text
    return response.json()


def create_sale(client, product_id, quantity):
    response = client.post(
        "/sales/",
        json={
            "customer_id": None,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": quantity,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_business_summary_returns_zero_totals_when_no_sales(client):
    response = client.get("/reports/summary")

    assert response.status_code == 200
    report = response.json()

    assert report["total_sales"] == 0
    assert Decimal(str(report["total_revenue"])) == Decimal("0")
    assert report["units_sold"] == 0
    assert report["active_products"] == 0
    assert report["active_customers"] == 0
    assert Decimal(str(report["inventory_value"])) == Decimal("0")


def test_business_summary_reflects_sales_and_inventory(client):
    product = create_product(
        client,
        price="25.00",
        stock_quantity=10,
    )

    create_sale(client, product["id"], quantity=2)

    response = client.get("/reports/summary")

    assert response.status_code == 200
    report = response.json()

    assert report["total_sales"] == 1
    assert Decimal(str(report["total_revenue"])) == Decimal("50.00")
    assert report["units_sold"] == 2
    assert report["active_products"] == 1

    # Two units were sold, leaving eight at R25 each.
    assert Decimal(str(report["inventory_value"])) == Decimal("200.00")


def test_top_products_ranks_by_units_sold(client):
    first_product = create_product(
        client,
        sku="REPORT-101",
        name="Popular Product",
        price="20.00",
    )
    second_product = create_product(
        client,
        sku="REPORT-102",
        name="Less Popular Product",
        price="30.00",
    )

    create_sale(client, first_product["id"], quantity=3)
    create_sale(client, second_product["id"], quantity=1)

    response = client.get("/reports/top-products")

    assert response.status_code == 200
    report = response.json()

    assert len(report) == 2
    assert report[0]["product_id"] == first_product["id"]
    assert report[0]["product_name"] == "Popular Product"
    assert report[0]["units_sold"] == 3
    assert Decimal(str(report[0]["revenue"])) == Decimal("60.00")


def test_top_products_respects_limit(client):
    first_product = create_product(
        client,
        sku="REPORT-201",
        name="Product One",
    )
    second_product = create_product(
        client,
        sku="REPORT-202",
        name="Product Two",
    )

    create_sale(client, first_product["id"], quantity=2)
    create_sale(client, second_product["id"], quantity=1)

    response = client.get("/reports/top-products?limit=1")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["product_id"] == first_product["id"]


def test_low_stock_report_returns_only_matching_active_products(client):
    low_stock_product = create_product(
        client,
        sku="REPORT-301",
        name="Low Stock Product",
        stock_quantity=2,
    )
    create_product(
        client,
        sku="REPORT-302",
        name="Well Stocked Product",
        stock_quantity=8,
    )
    create_product(
        client,
        sku="REPORT-303",
        name="Inactive Product",
        stock_quantity=1,
        is_active=False,
    )

    response = client.get("/reports/low-stock?threshold=3")

    assert response.status_code == 200
    report = response.json()

    assert len(report) == 1
    assert report[0]["product_id"] == low_stock_product["id"]
    assert report[0]["stock_quantity"] == 2
    assert Decimal(str(report[0]["inventory_value"])) == Decimal("50.00")


def test_summary_rejects_invalid_date_range(client):
    response = client.get(
        "/reports/summary",
        params={
            "start_date": "2026-10-20",
            "end_date": "2026-10-19",
        },
    )

    assert response.status_code == 400


def test_top_products_rejects_invalid_limit(client):
    response = client.get("/reports/top-products?limit=0")

    assert response.status_code == 422