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


def sample_product(**overrides):
    product = {
        "sku": "SALE-001",
        "name": "Business Laptop",
        "description": "Laptop for business operations",
        "category": "Computers",
        "price": "100.00",
        "stock_quantity": 10,
        "is_active": True,
    }
    product.update(overrides)
    return product


def create_product(client, **overrides):
    response = client.post(
        "/products/",
        json=sample_product(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def sample_customer(**overrides):
    customer = {
        "full_name": "Test Customer",
        "email": "customer@example.com",
        "phone": "0123456789",
        "company": "Example Company",
        "notes": "Created for sales testing",
        "is_active": True,
    }
    customer.update(overrides)
    return customer


def create_customer(client, **overrides):
    response = client.post(
        "/customers/",
        json=sample_customer(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_sale_payload(product_id, quantity=1, customer_id=None):
    return {
        "customer_id": customer_id,
        "items": [
            {
                "product_id": product_id,
                "quantity": quantity,
            }
        ],
    }


def test_create_sale_calculates_total_and_deducts_stock(client):
    product = create_product(
        client,
        price="100.00",
        stock_quantity=10,
    )

    response = client.post(
        "/sales/",
        json=create_sale_payload(product["id"], quantity=2),
    )

    assert response.status_code == 201, response.text

    sale = response.json()

    assert sale["id"] > 0
    assert sale["customer_id"] is None
    assert Decimal(str(sale["total_amount"])) == Decimal("200.00")
    assert len(sale["items"]) == 1

    item = sale["items"][0]
    assert item["product_id"] == product["id"]
    assert item["product_name"] == product["name"]
    assert item["sku"] == product["sku"]
    assert item["quantity"] == 2
    assert Decimal(str(item["unit_price"])) == Decimal("100.00")
    assert Decimal(str(item["line_total"])) == Decimal("200.00")

    products_response = client.get("/products/")
    assert products_response.status_code == 200

    updated_product = next(
        p for p in products_response.json()
        if p["id"] == product["id"]
    )
    assert updated_product["stock_quantity"] == 8


def test_sale_records_stock_out_transaction(client):
    product = create_product(client, stock_quantity=5)

    sale_response = client.post(
        "/sales/",
        json=create_sale_payload(product["id"], quantity=2),
    )
    assert sale_response.status_code == 201, sale_response.text

    history_response = client.get(
        f"/inventory/products/{product['id']}/transactions"
    )
    assert history_response.status_code == 200

    history = history_response.json()
    assert len(history) == 2
    opening = next(item for item in history if item["reason"] == "Opening stock")
    sale_movement = next(
        item for item in history
        if item["reason"] == f"Sale #{sale_response.json()['id']}"
    )
    assert opening["movement_type"] == "stock_in"
    assert opening["quantity_change"] == 5
    assert sale_movement["product_id"] == product["id"]
    assert sale_movement["movement_type"] == "stock_out"
    assert sale_movement["quantity_change"] == -2


def test_sale_uses_product_price_and_preserves_price_snapshot(client):
    product = create_product(
        client,
        price="49.99",
        stock_quantity=5,
    )

    sale_response = client.post(
        "/sales/",
        json=create_sale_payload(product["id"], quantity=3),
    )
    assert sale_response.status_code == 201, sale_response.text

    sale = sale_response.json()
    assert Decimal(str(sale["total_amount"])) == Decimal("149.97")
    assert Decimal(str(sale["items"][0]["unit_price"])) == Decimal("49.99")
    assert Decimal(str(sale["items"][0]["line_total"])) == Decimal("149.97")

    # Change the product's current price after the sale.
    update_response = client.patch(
        f"/products/{product['id']}",
        json={"price": "60.00"},
    )
    assert update_response.status_code == 200, update_response.text

    # The historical sale must retain the original price.
    detail_response = client.get(f"/sales/{sale['id']}")
    assert detail_response.status_code == 200

    saved_sale = detail_response.json()
    assert Decimal(str(saved_sale["total_amount"])) == Decimal("149.97")
    assert Decimal(str(saved_sale["items"][0]["unit_price"])) == Decimal("49.99")


def test_sale_can_be_linked_to_active_customer(client):
    product = create_product(client)
    customer = create_customer(client)

    response = client.post(
        "/sales/",
        json=create_sale_payload(
            product["id"],
            quantity=1,
            customer_id=customer["id"],
        ),
    )

    assert response.status_code == 201, response.text
    assert response.json()["customer_id"] == customer["id"]


def test_sale_rejects_nonexistent_product_without_creating_sale(client):
    response = client.post(
        "/sales/",
        json=create_sale_payload(product_id=999999),
    )

    assert response.status_code == 404

    sales_response = client.get("/sales/")
    assert sales_response.status_code == 200
    assert sales_response.json() == []


def test_sale_rejects_inactive_product_without_deducting_stock(client):
    product = create_product(
        client,
        stock_quantity=5,
        is_active=False,
    )

    response = client.post(
        "/sales/",
        json=create_sale_payload(product["id"], quantity=1),
    )

    assert response.status_code == 400

    products_response = client.get("/products/?include_inactive=true")
    assert products_response.status_code == 200

    saved_product = next(
        p for p in products_response.json()
        if p["id"] == product["id"]
    )
    assert saved_product["stock_quantity"] == 5

    assert client.get("/sales/").json() == []
    inactive_history = client.get(
        f"/inventory/products/{product['id']}/transactions"
    ).json()
    assert len(inactive_history) == 1
    assert inactive_history[0]["reason"] == "Opening stock"


def test_sale_rejects_nonexistent_customer(client):
    product = create_product(client)

    response = client.post(
        "/sales/",
        json=create_sale_payload(
            product["id"],
            customer_id=999999,
        ),
    )

    assert response.status_code == 404
    assert client.get("/sales/").json() == []


def test_sale_rejects_inactive_customer(client):
    product = create_product(client)
    customer = create_customer(client)

    # Deactivate the customer through the customer API.
    deactivate_response = client.delete(
        f"/customers/{customer['id']}"
    )
    assert deactivate_response.status_code in (200, 204), (
        deactivate_response.text
    )

    # Verify that the sale endpoint rejects the inactive customer.
    response = client.post(
        "/sales/",
        json=create_sale_payload(
            product["id"],
            customer_id=customer["id"],
        ),
    )

    assert response.status_code == 400
    assert client.get("/sales/").json() == []


def test_insufficient_stock_creates_no_sale_or_transaction(client):
    product = create_product(
        client,
        stock_quantity=2,
    )

    response = client.post(
        "/sales/",
        json=create_sale_payload(product["id"], quantity=3),
    )

    assert response.status_code == 409
    assert client.get("/sales/").json() == []

    products_response = client.get("/products/")
    saved_product = next(
        p for p in products_response.json()
        if p["id"] == product["id"]
    )
    assert saved_product["stock_quantity"] == 2

    history_response = client.get(
        f"/inventory/products/{product['id']}/transactions"
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 1
    assert history[0]["reason"] == "Opening stock"
    assert history[0]["quantity_change"] == 2


def test_sale_list_and_detail_endpoints(client):
    product = create_product(client)

    create_response = client.post(
        "/sales/",
        json=create_sale_payload(product["id"]),
    )
    assert create_response.status_code == 201
    sale_id = create_response.json()["id"]

    list_response = client.get("/sales/")
    assert list_response.status_code == 200
    assert any(
        sale["id"] == sale_id
        for sale in list_response.json()
    )

    detail_response = client.get(f"/sales/{sale_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == sale_id
    assert len(detail_response.json()["items"]) == 1


def test_get_nonexistent_sale_returns_404(client):
    response = client.get("/sales/999999")
    assert response.status_code == 404


def test_sale_rejects_duplicate_product_lines(client):
    product = create_product(client, stock_quantity=10)

    response = client.post(
        "/sales/",
        json={
            "customer_id": None,
            "items": [
                {"product_id": product["id"], "quantity": 1},
                {"product_id": product["id"], "quantity": 2},
            ],
        },
    )

    assert response.status_code == 422
    assert client.get("/sales/").json() == []
