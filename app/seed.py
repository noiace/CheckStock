"""Initial demo data; existing products and warehouse balances are never reset."""
import asyncio

from sqlalchemy import select, text

from db.database import AsyncSessionLocal, engine
from models.product import Product
from models.warehouse import Warehouse
from services.inventory import receive_stock


async def seed() -> None:
    async with AsyncSessionLocal() as session, session.begin():
        # Serialize concurrent initial starts without adding a seed-marker table.
        await session.execute(text("SELECT pg_advisory_xact_lock(101103)"))
        if await session.scalar(select(Product.id).limit(1)) is not None or await session.scalar(
            select(Warehouse.id).limit(1)
        ) is not None:
            return
        warehouses = []
        for name in ("Север", "Юг"):
            warehouse = Warehouse(name=name, is_active=True)
            session.add(warehouse)
            await session.flush()
            warehouses.append(warehouse)

        for sku, name, quantities in (
            ("SKU-101", "Органайзер", (10, 6)),
            ("SKU-102", "Контейнер", (5, 0)),
            ("SKU-103", "Корзина", (0, 4)),
        ):
            product = Product(sku=sku, name=name)
            session.add(product)
            await session.flush()
            for warehouse, quantity in zip(warehouses, quantities):
                if quantity:
                    await receive_stock(session, product.id, warehouse.id, quantity)


async def main() -> None:
    try:
        await seed()
        print("Демо-данные готовы; существующие остатки сохранены.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
