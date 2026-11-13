from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.reports import router
from app.db.base import Base
from app.db.session import get_db
from app.models.customer import Customer
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.sale import Sale, SaleItem


def create_test_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app), TestingSessionLocal, engine, app


def add_product(db, sku, name, quantity, price=10, is_active=True):
    product = Product(
        sku=sku,
        name=name,
        category="Test",
        price=price,
        stock_quantity=quantity,
        is_active=is_active,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def test_inventory_health_counts_actual_stock_units():
    client, session_factory, engine, app = create_test_client()

    try:
        with session_factory() as db:
            add_product(db, "HEALTH-001", "Healthy Product", 20)
            add_product(db, "HEALTH-002", "Low Stock Product", 3)
            add_product(db, "HEALTH-003", "Out of Stock Product", 0)

        response = client.get("/reports/inventory-health")

        assert response.status_code == 200
        data = response.json()

        assert data["threshold"] == 5
        assert data["active_products"] == 3
        assert data["total_stock_units"] == 23
        assert data["low_stock_units"] == 3
        assert data["healthy_stock_units"] == 20
        assert data["low_stock_products"] == 2
        assert data["healthy_stock_products"] == 1
        assert float(data["inventory_value"]) == 230.0
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_inventory_health_excludes_inactive_products():
    client, session_factory, engine, app = create_test_client()

    try:
        with session_factory() as db:
            add_product(db, "HEALTH-004", "Active Product", 8)
            add_product(
                db,
                "HEALTH-005",
                "Inactive Product",
                100,
                is_active=False,
            )

        response = client.get("/reports/inventory-health")

        assert response.status_code == 200
        data = response.json()

        assert data["active_products"] == 1
        assert data["total_stock_units"] == 8
        assert data["healthy_stock_units"] == 8
        assert data["low_stock_units"] == 0
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_inventory_health_supports_custom_threshold():
    client, session_factory, engine, app = create_test_client()

    try:
        with session_factory() as db:
            add_product(db, "HEALTH-006", "Threshold Product", 8)

        response = client.get(
            "/reports/inventory-health",
            params={"threshold": 10},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["threshold"] == 10
        assert data["low_stock_products"] == 1
        assert data["low_stock_units"] == 8
        assert data["healthy_stock_products"] == 0
        assert data["healthy_stock_units"] == 0
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_inventory_health_rejects_negative_threshold():
    client, session_factory, engine, app = create_test_client()

    try:
        response = client.get(
            "/reports/inventory-health",
            params={"threshold": -1},
        )

        assert response.status_code == 422
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()