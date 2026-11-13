"""Seed a clearly labelled, repeatable demo dataset.

Run from the project root with the virtual environment active:
    python seed_demo_data.py

The script refuses to run if any DEMO-* product already exists. It never
deletes or overwrites existing business records.
"""
from datetime import datetime, timedelta
from decimal import Decimal
import random

from sqlalchemy import select

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.customer import Customer
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.sale import Sale, SaleItem

DEMO_PRODUCTS = [
    ("DEMO-001", "Business Laptop Pro", "Computers", "18999.00", 65),
    ("DEMO-002", "Office Monitor 27-inch", "Displays", "4299.00", 58),
    ("DEMO-003", "Wireless Keyboard", "Accessories", "699.00", 80),
    ("DEMO-004", "Wireless Mouse", "Accessories", "399.00", 90),
    ("DEMO-005", "USB-C Docking Station", "Accessories", "1899.00", 42),
    ("DEMO-006", "Network Switch 24-Port", "Networking", "3499.00", 35),
    ("DEMO-007", "Wi-Fi 6 Access Point", "Networking", "2299.00", 40),
    ("DEMO-008", "External SSD 1TB", "Storage", "1599.00", 52),
    ("DEMO-009", "Laptop Charger 65W", "Accessories", "549.00", 4),
    ("DEMO-010", "HDMI Adapter", "Accessories", "249.00", 0),
]

DEMO_CUSTOMERS = [
    ("Thando Mbeki", "thando.mbeki@example.com", "Cape Town Office Supplies"),
    ("Lerato Nkosi", "lerato.nkosi@example.com", "Nkosi Consulting"),
    ("Aiden Jacobs", "aiden.jacobs@example.com", "Jacobs Design Studio"),
    ("Zanele Dlamini", "zanele.dlamini@example.com", "Dlamini Technologies"),
    ("Mia Daniels", "mia.daniels@example.com", "Daniels Accounting"),
    ("Sipho Khumalo", "sipho.khumalo@example.com", "Khumalo Trading"),
    ("Amara Petersen", "amara.petersen@example.com", "Petersen Solutions"),
    ("Noah Williams", "noah.williams@example.com", "Williams Logistics"),
]


def main():
    Base.metadata.create_all(bind=engine)
    rng = random.Random(20261023)
    now = datetime.now().replace(microsecond=0)

    with SessionLocal() as db:
        existing_demo = db.scalar(
            select(Product.id).where(Product.sku.like("DEMO-%")).limit(1)
        )
        if existing_demo is not None:
            print("Demo products already exist. No records were changed.")
            print("To avoid duplicating sales, this script stopped safely.")
            return

        products = []
        for sku, name, category, price, opening_stock in DEMO_PRODUCTS:
            product = Product(
                sku=sku,
                name=name,
                description="Clearly labelled sample record for portfolio demonstration.",
                category=category,
                price=Decimal(price),
                stock_quantity=opening_stock,
                is_active=True,
            )
            db.add(product)
            products.append(product)

        customers = []
        for full_name, email, company in DEMO_CUSTOMERS:
            customer = Customer(
                full_name=full_name,
                email=email,
                company=company,
                phone=None,
                notes="Demo customer created by seed_demo_data.py",
                is_active=True,
            )
            db.add(customer)
            customers.append(customer)

        db.flush()

        # Record each opening balance so the inventory history starts with
        # a documented movement instead of unexplained stock quantities.
        for product in products:
            if product.stock_quantity > 0:
                db.add(
                    InventoryTransaction(
                        product_id=product.id,
                        movement_type="stock_in",
                        quantity_change=product.stock_quantity,
                        reason="Opening stock (demo data)",
                        created_at=now - timedelta(days=50),
                    )
                )

        sales_created = 0
        for sale_index in range(30):
            # Spread sales across the last 45 days, including the current month.
            days_ago = (sale_index * 13) % 45
            sold_at = now - timedelta(days=days_ago, hours=(sale_index * 3) % 12)
            customer = customers[sale_index % len(customers)]

            eligible_products = products[:8]
            line_count = rng.randint(1, 3)
            chosen = rng.sample(eligible_products, line_count)
            sale_items = []
            movements = []
            total = Decimal("0.00")

            for product in chosen:
                quantity = rng.randint(1, 3)
                if product.stock_quantity < quantity:
                    quantity = product.stock_quantity
                if quantity <= 0:
                    continue

                unit_price = Decimal(product.price)
                line_total = (unit_price * quantity).quantize(Decimal("0.01"))
                sale_items.append(
                    SaleItem(
                        product_id=product.id,
                        product_name=product.name,
                        sku=product.sku,
                        quantity=quantity,
                        unit_price=unit_price,
                        line_total=line_total,
                    )
                )
                total += line_total
                product.stock_quantity -= quantity
                movements.append((product.id, quantity))

            if not sale_items:
                continue

            sale = Sale(
                customer_id=customer.id,
                total_amount=total,
                created_at=sold_at,
                items=sale_items,
            )
            db.add(sale)
            db.flush()
            for product_id, quantity in movements:
                db.add(
                    InventoryTransaction(
                        product_id=product_id,
                        movement_type="stock_out",
                        quantity_change=-quantity,
                        reason=f"Sale #{sale.id} (demo data)",
                        created_at=sold_at,
                    )
                )
            sales_created += 1

        db.commit()

        print("Demo dataset created successfully.")
        print(f"Products: {len(products)}")
        print(f"Customers: {len(customers)}")
        print(f"Sales: {sales_created}")
        print("Opening stock and sale movements were recorded in inventory history.")
        print("All generated records use DEMO-* SKUs and are sample data.")


if __name__ == "__main__":
    main()
