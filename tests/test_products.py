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
    # Use an isolated in-memory database for tests.
    # These tests will not create or modify product records
    # in your PostgreSQL development database.
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

    # Do not use TestClient as a context manager here:
    # the application's startup lifespan should not run.
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()
        test_engine.dispose()


def sample_product(**overrides):
    product = {
        "sku": "TEST-001",
        "name": "Test Laptop",
        "description": "Laptop used for automated API testing",
        "category": "Computers",
        "price": 12000.00,
        "stock_quantity": 10,
        "is_active": True,
    }
    product.update(overrides)
    return product


def test_create_product(client):
    response = client.post(
        "/products/",
        json=sample_product(),
    )

    assert response.status_code == 201

    data = response.json()
    assert data["id"] is not None
    assert data["sku"] == "TEST-001"
    assert data["name"] == "Test Laptop"
    assert data["stock_quantity"] == 10
    assert data["is_active"] is True


def test_list_products(client):
    client.post("/products/", json=sample_product())

    response = client.get("/products/")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["sku"] == "TEST-001"


def test_duplicate_sku_is_rejected(client):
    first = client.post(
        "/products/",
        json=sample_product(),
    )
    second = client.post(
        "/products/",
        json=sample_product(name="Another Laptop"),
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_negative_stock_is_rejected(client):
    response = client.post(
        "/products/",
        json=sample_product(
            sku="TEST-002",
            stock_quantity=-5,
        ),
    )

    assert response.status_code == 422


def test_get_missing_product_returns_404(client):
    response = client.get("/products/99999")

    assert response.status_code == 404


def test_update_product(client):
    created = client.post(
        "/products/",
        json=sample_product(),
    )
    product_id = created.json()["id"]

    response = client.patch(
        f"/products/{product_id}",
        json={"price": 13500.00},
    )

    assert response.status_code == 200
    assert float(response.json()["price"]) == 13500.00
    assert response.json()["stock_quantity"] == 10

    # Stock must be changed through inventory transactions so the
    # inventory history remains auditable.
    stock_update = client.patch(
        f"/products/{product_id}",
        json={"stock_quantity": 20},
    )
    assert stock_update.status_code == 422

    unchanged = client.get(f"/products/{product_id}")
    assert unchanged.json()["stock_quantity"] == 10


def test_deactivate_product(client):
    created = client.post(
        "/products/",
        json=sample_product(),
    )
    product_id = created.json()["id"]

    response = client.delete(f"/products/{product_id}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Inactive products should be hidden from the default listing.
    listing = client.get("/products/")

    assert listing.status_code == 200
    assert listing.json() == []


def test_invalid_price_is_rejected(client):
    response = client.post(
        "/products/",
        json=sample_product(
            sku="TEST-003",
            price=-100.00,
        ),
    )

    assert response.status_code == 422
