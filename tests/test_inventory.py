import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
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
        test_engine.dispose()


@pytest.fixture
def product_id(client):
    response = client.post(
        "/products/",
        json={
            "sku": "INV-TEST-001",
            "name": "Inventory Test Product",
            "description": "Product used in inventory tests",
            "category": "Test Items",
            "price": 100.00,
            "stock_quantity": 10,
            "is_active": True,
        },
    )

    assert response.status_code == 201
    return response.json()["id"]


def record_movement(
    client,
    product_id,
    movement_type,
    quantity,
    reason="Automated inventory test",
    adjustment_direction=None,
):
    payload = {
        "product_id": product_id,
        "movement_type": movement_type,
        "quantity": quantity,
        "reason": reason,
    }

    if adjustment_direction is not None:
        payload["adjustment_direction"] = adjustment_direction

    return client.post("/inventory/transactions", json=payload)


def get_stock(client, product_id):
    response = client.get(f"/products/{product_id}")
    assert response.status_code == 200
    return response.json()["stock_quantity"]


def test_stock_in_increases_quantity(client, product_id):
    response = record_movement(
        client, product_id, "stock_in", 5
    )

    assert response.status_code == 201
    assert response.json()["quantity_change"] == 5
    assert get_stock(client, product_id) == 15


def test_stock_out_decreases_quantity(client, product_id):
    response = record_movement(
        client, product_id, "stock_out", 3
    )

    assert response.status_code == 201
    assert response.json()["quantity_change"] == -3
    assert get_stock(client, product_id) == 7


def test_insufficient_stock_is_rejected(client, product_id):
    response = record_movement(
        client, product_id, "stock_out", 11
    )

    assert response.status_code == 409
    assert get_stock(client, product_id) == 10


def test_failed_stock_out_does_not_create_transaction(client, product_id):
    response = record_movement(
        client, product_id, "stock_out", 50
    )

    assert response.status_code == 409

    history = client.get(
        f"/inventory/products/{product_id}/transactions"
    )

    assert history.status_code == 200
    transactions = history.json()
    assert len(transactions) == 1
    assert transactions[0]["movement_type"] == "stock_in"
    assert transactions[0]["quantity_change"] == 10
    assert transactions[0]["reason"] == "Opening stock"


def test_inventory_history_records_movements(client, product_id):
    record_movement(client, product_id, "stock_in", 5)
    record_movement(client, product_id, "stock_out", 2)

    response = client.get(
        f"/inventory/products/{product_id}/transactions"
    )

    assert response.status_code == 200
    transactions = response.json()
    assert len(transactions) == 3
    assert {item["quantity_change"] for item in transactions} == {10, 5, -2}


def test_adjustment_increases_stock(client, product_id):
    response = record_movement(
        client,
        product_id,
        "adjustment",
        4,
        adjustment_direction="increase",
    )

    assert response.status_code == 201
    assert response.json()["quantity_change"] == 4
    assert get_stock(client, product_id) == 14


def test_adjustment_decreases_stock(client, product_id):
    response = record_movement(
        client,
        product_id,
        "adjustment",
        4,
        adjustment_direction="decrease",
    )

    assert response.status_code == 201
    assert response.json()["quantity_change"] == -4
    assert get_stock(client, product_id) == 6


def test_adjustment_cannot_make_stock_negative(client, product_id):
    response = record_movement(
        client,
        product_id,
        "adjustment",
        11,
        adjustment_direction="decrease",
    )

    assert response.status_code == 409
    assert get_stock(client, product_id) == 10
