import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url


# Refuse destructive test cleanup unless all coordinates match the isolated service.
url = make_url(os.environ["DATABASE_URL"])
if (url.drivername, url.host, url.database, url.username) != (
    "postgresql+asyncpg", "postgres-test", "checkstock_test", "checkstock_test",
):
    raise RuntimeError("Тесты разрешены только на postgres-test/checkstock_test из compose.test.yml")

from db.database import AsyncSessionLocal, engine
from main import app


@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    async with engine.begin() as connection:
        await connection.execute(text(
            "TRUNCATE stock_movements, fbs_reservations, fbo_shipments, transfers, "
            "stocks, products, warehouses RESTART IDENTITY CASCADE"
        ))
    yield
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def inventory(client):
    product = (await client.post("/products", json={"sku": "TEST-1", "name": "Товар"})).json()
    north = (await client.post("/warehouses", json={"name": "Север"})).json()
    south = (await client.post("/warehouses", json={"name": "Юг"})).json()
    response = await client.post("/receipts", json={
        "product_id": product["id"], "warehouse_id": north["id"], "quantity": 10,
    })
    assert response.status_code == 201, response.text
    return product["id"], north["id"], south["id"]
