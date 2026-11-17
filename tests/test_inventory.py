import asyncio

import pytest
from sqlalchemy import event, func, select, text

from db.database import AsyncSessionLocal, engine
from models.fbo_shipment import FBOShipment
from models.fbs_reservation import FBSReservation
from models.product import Product
from models.stock import Stock
from models.stock_movement import StockMovement, StockMovementType
from models.transfer import Transfer
from models.warehouse import Warehouse
from seed import seed


async def balance(product_id, warehouse_id):
    async with AsyncSessionLocal() as session:
        row = await session.scalar(select(Stock).where(
            Stock.product_id == product_id, Stock.warehouse_id == warehouse_id,
        ))
        return (row.physical_quantity, row.reserved_quantity) if row else (0, 0)


async def movements():
    async with AsyncSessionLocal() as session:
        return list((await session.scalars(select(StockMovement).order_by(StockMovement.id))).all())


async def count(model):
    async with AsyncSessionLocal() as session:
        return await session.scalar(select(func.count()).select_from(model))


def payload(inventory, quantity=3, transfer=False):
    product, north, south = inventory
    if transfer:
        return dict(product_id=product, from_warehouse_id=north, to_warehouse_id=south, quantity=quantity)
    return dict(product_id=product, warehouse_id=north, quantity=quantity)


async def create(client, path, data):
    response = await client.post(path, json=data)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_receipts_and_zero_overview(client, inventory):
    product, north, south = inventory
    await create(client, "/receipts", payload(inventory, 2))
    assert await balance(product, north) == (12, 0)
    response = await client.get(f"/stocks/{product}")
    assert response.status_code == 200
    rows = {row["warehouse_id"]: row for row in response.json()}
    assert rows[north]["available_quantity"] == 12
    assert rows[south]["physical_quantity"] == rows[south]["available_quantity"] == 0
    history = await movements()
    assert [(h.movement_type, h.quantity, h.from_warehouse_id, h.to_warehouse_id) for h in history] == [
        (StockMovementType.RECEIPT, 10, None, north),
        (StockMovementType.RECEIPT, 2, None, north),
    ]


@pytest.mark.parametrize("path", ["/receipts", "/fbs/reservations", "/fbo/shipments", "/transfers"])
@pytest.mark.parametrize("quantity", [0, -1, 1.5])
async def test_invalid_quantity(client, inventory, path, quantity):
    response = await client.post(path, json=payload(inventory, quantity, path == "/transfers"))
    assert response.status_code == 422
    assert await balance(*inventory[:2]) == (10, 0)
    assert await count(StockMovement) == 1


@pytest.mark.parametrize("path", ["/receipts", "/fbs/reservations", "/fbo/shipments", "/transfers"])
@pytest.mark.parametrize("missing", ["product", "warehouse"])
async def test_missing_objects(client, inventory, path, missing):
    data = payload(inventory, transfer=path == "/transfers")
    key = "product_id" if missing == "product" else ("from_warehouse_id" if path == "/transfers" else "warehouse_id")
    data[key] = 999999
    response = await client.post(path, json=data)
    assert response.status_code == 404, response.text
    assert await balance(*inventory[:2]) == (10, 0)
    assert await count(StockMovement) == 1


@pytest.mark.parametrize("path", ["/fbs/reservations", "/fbo/shipments", "/transfers"])
async def test_shortage_on_selected_warehouse(client, inventory, path):
    product, north, south = inventory
    await create(client, "/receipts", dict(product_id=product, warehouse_id=south, quantity=20))
    response = await client.post(path, json=payload(inventory, 11, path == "/transfers"))
    assert response.status_code == 409, response.text
    assert await balance(product, north) == (10, 0)
    assert await balance(product, south) == (20, 0)
    assert await count(StockMovement) == 2


async def test_fbs_ship_deliver_and_repeats(client, inventory):
    product, north, _ = inventory
    operation = await create(client, "/fbs/reservations", payload(inventory))
    assert await balance(product, north) == (10, 3)
    rows = (await client.get(f"/stocks/{product}")).json()
    assert next(row for row in rows if row["warehouse_id"] == north)["available_quantity"] == 7
    assert (await client.get("/movements/in-transit")).json() == []
    for _ in range(2):
        response = await client.post(f"/fbs/reservations/{operation}/ship")
        assert response.status_code == 200 and response.json()["status"] == "SHIPPED"
        assert response.json()["shipped_at"]
        assert await balance(product, north) == (7, 0)
    transit = (await client.get("/movements/in-transit")).json()
    assert [(t["kind"], t["quantity"]) for t in transit] == [("FBS", 3)]
    assert (await client.post(f"/fbs/reservations/{operation}/cancel")).status_code == 409
    for _ in range(2):
        response = await client.post(f"/fbs/reservations/{operation}/deliver")
        assert response.status_code == 200 and response.json()["status"] == "DELIVERED"
        assert response.json()["delivered_at"]
    assert (await client.post(f"/fbs/reservations/{operation}/ship")).status_code == 200
    assert (await client.get("/movements/in-transit")).json() == []
    assert await balance(product, north) == (7, 0)
    history = await movements()
    assert [h.movement_type.value for h in history] == ["RECEIPT", "FBS_RESERVED", "FBS_SHIPPED", "FBS_DELIVERED"]
    assert all(h.quantity == 3 and h.fbs_reservation_id == operation and h.from_warehouse_id == north for h in history[1:])
    async with AsyncSessionLocal() as session:
        assert (await session.get(FBSReservation, operation)).status.value == "DELIVERED"


async def test_fbs_cancel_and_invalid_transitions(client, inventory):
    operation = await create(client, "/fbs/reservations", payload(inventory))
    assert (await client.post(f"/fbs/reservations/{operation}/deliver")).status_code == 409
    for _ in range(2):
        response = await client.post(f"/fbs/reservations/{operation}/cancel")
        assert response.status_code == 200 and response.json()["cancelled_at"]
    assert (await client.post(f"/fbs/reservations/{operation}/ship")).status_code == 409
    assert (await client.post(f"/fbs/reservations/{operation}/deliver")).status_code == 409
    assert await balance(*inventory[:2]) == (10, 0)
    history = await movements()
    assert [h.movement_type.value for h in history] == ["RECEIPT", "FBS_RESERVED", "FBS_CANCELLED"]
    assert history[-1].quantity == 3 and history[-1].to_warehouse_id == inventory[1]


@pytest.mark.parametrize("path", ["/fbs/reservations", "/fbo/shipments", "/transfers"])
async def test_reserved_stock_cannot_be_used(client, inventory, path):
    await create(client, "/fbs/reservations", payload(inventory, 8))
    response = await client.post(path, json=payload(inventory, 3, path == "/transfers"))
    assert response.status_code == 409
    assert await balance(*inventory[:2]) == (10, 8)
    assert await count(StockMovement) == 2


async def test_fbo_receive_and_repeat(client, inventory):
    operation = await create(client, "/fbo/shipments", payload(inventory))
    assert await balance(*inventory[:2]) == (7, 0)
    transit = (await client.get("/movements/in-transit")).json()
    assert [(t["kind"], t["operation_id"], t["quantity"]) for t in transit] == [("FBO", operation, 3)]
    for _ in range(2):
        response = await client.post(f"/fbo/shipments/{operation}/receive")
        assert response.status_code == 200 and response.json()["received_at"]
    assert (await client.get("/movements/in-transit")).json() == []
    assert await balance(*inventory[:2]) == (7, 0)
    history = await movements()
    assert [h.movement_type.value for h in history] == ["RECEIPT", "FBO_SHIPPED", "FBO_RECEIVED"]
    assert all(h.quantity == 3 and h.from_warehouse_id == inventory[1] and h.fbo_shipment_id == operation for h in history[1:])
    async with AsyncSessionLocal() as session:
        assert (await session.get(FBOShipment, operation)).status.value == "RECEIVED"


async def test_transfer_receive_and_repeat(client, inventory):
    product, north, south = inventory
    operation = await create(client, "/transfers", payload(inventory, 5, True))
    assert await balance(product, north) == (5, 0)
    assert await balance(product, south) == (0, 0)
    transit = (await client.get("/movements/in-transit")).json()
    assert [(t["kind"], t["from_warehouse_id"], t["to_warehouse_id"], t["quantity"]) for t in transit] == [("TRANSFER", north, south, 5)]
    for _ in range(2):
        response = await client.post(f"/transfers/{operation}/receive")
        assert response.status_code == 200 and response.json()["received_at"]
    assert await balance(product, north) == (5, 0)
    assert await balance(product, south) == (5, 0)
    assert (await client.get("/movements/in-transit")).json() == []
    history = await movements()
    assert [h.movement_type.value for h in history] == ["RECEIPT", "TRANSFER_SHIPPED", "TRANSFER_RECEIVED"]
    assert all(h.quantity == 5 and h.from_warehouse_id == north and h.to_warehouse_id == south and h.transfer_id == operation for h in history[1:])
    async with AsyncSessionLocal() as session:
        assert (await session.get(Transfer, operation)).status.value == "RECEIVED"


async def test_transfer_to_same_warehouse(client, inventory):
    data = payload(inventory, transfer=True)
    data["to_warehouse_id"] = data["from_warehouse_id"]
    assert (await client.post("/transfers", json=data)).status_code == 422
    assert await balance(*inventory[:2]) == (10, 0)
    assert await count(StockMovement) == 1


async def test_warehouse_archive_preserves_data(client, inventory):
    product, north, _ = inventory
    assert (await client.patch(f"/warehouses/{north}", json={"name": "Север новый"})).status_code == 200
    for _ in range(2):
        response = await client.delete(f"/warehouses/{north}")
        assert response.status_code == 200 and response.json()["is_active"] is False
    assert await balance(product, north) == (10, 0)
    assert await count(StockMovement) == 1
    assert len((await client.get("/warehouses?active_only=true")).json()) == 1
    assert len((await client.get("/warehouses")).json()) == 2
    assert (await client.get(f"/warehouses/{north}")).json()["name"] == "Север новый"
    row = next(row for row in (await client.get("/stocks")).json() if row["warehouse_id"] == north)
    assert row["warehouse_is_active"] is False and row["physical_quantity"] == 10
    assert (await client.patch(f"/warehouses/{north}", json={"name": "Новое"})).status_code == 409


@pytest.mark.parametrize("path", ["/receipts", "/fbs/reservations", "/fbo/shipments", "/transfers"])
async def test_archive_blocks_new_operations(client, inventory, path):
    await client.delete(f"/warehouses/{inventory[1]}")
    response = await client.post(path, json=payload(inventory, transfer=path == "/transfers"))
    assert response.status_code == 409
    assert await balance(*inventory[:2]) == (10, 0)
    assert await count(StockMovement) == 1


async def test_existing_operations_can_finish_after_archive(client, inventory):
    fbs = await create(client, "/fbs/reservations", payload(inventory, 2))
    fbo = await create(client, "/fbo/shipments", payload(inventory, 2))
    transfer = await create(client, "/transfers", payload(inventory, 2, True))
    await client.delete(f"/warehouses/{inventory[1]}")
    await client.delete(f"/warehouses/{inventory[2]}")
    for path in (f"/fbs/reservations/{fbs}/ship", f"/fbs/reservations/{fbs}/deliver", f"/fbo/shipments/{fbo}/receive", f"/transfers/{transfer}/receive"):
        assert (await client.post(path)).status_code == 200
    assert await balance(*inventory[:2]) == (4, 0)
    assert await balance(inventory[0], inventory[2]) == (2, 0)
    assert await count(StockMovement) == 8


@pytest.mark.parametrize("path", ["/fbs/reservations/999/ship", "/fbs/reservations/999/cancel", "/fbs/reservations/999/deliver", "/fbo/shipments/999/receive", "/transfers/999/receive"])
async def test_missing_operations(client, path):
    assert (await client.post(path)).status_code == 404


async def test_products_and_names(client):
    for data in ({"sku": " ", "name": "Товар"}, {"sku": "A", "name": " "}):
        assert (await client.post("/products", json=data)).status_code == 422
    await create(client, "/products", {"sku": " A ", "name": " Товар "})
    assert (await client.post("/products", json={"sku": "A", "name": "Дубликат"})).status_code == 409
    assert (await client.get("/products")).json()[0]["name"] == "Товар"
    assert (await client.post("/warehouses", json={"name": " "})).status_code == 422
    warehouse = await create(client, "/warehouses", {"name": " Север "})
    assert (await client.post("/warehouses", json={"name": "север"})).status_code == 409
    assert (await client.patch(f"/warehouses/{warehouse}", json={"name": " "})).status_code == 422
    assert (await client.get("/stocks/999")).status_code == 404


async def test_history_filters_and_pagination(client, inventory):
    await create(client, "/fbo/shipments", payload(inventory))
    rows = (await client.get(f"/movements?warehouse_id={inventory[1]}&product_id={inventory[0]}&movement_type=FBO_SHIPPED")).json()
    assert len(rows) == 1 and rows[0]["quantity"] == 3
    latest = (await client.get("/movements?limit=1")).json()
    older = (await client.get("/movements?limit=1&offset=1")).json()
    assert latest[0]["movement_type"] == "FBO_SHIPPED" and older[0]["movement_type"] == "RECEIPT"
    assert (await client.get("/movements?warehouse_id=999")).json() == []


async def test_seed_is_exact_and_does_not_replenish(client):
    await seed()
    assert await count(Product) == 3 and await count(Warehouse) == 2
    rows = (await client.get("/stocks")).json()
    expected = {("SKU-101", "Север"): 10, ("SKU-101", "Юг"): 6, ("SKU-102", "Север"): 5, ("SKU-102", "Юг"): 0, ("SKU-103", "Север"): 0, ("SKU-103", "Юг"): 4}
    assert {(r["sku"], r["warehouse_name"]): r["physical_quantity"] for r in rows} == expected
    await create(client, "/fbo/shipments", {"product_id": 1, "warehouse_id": 1, "quantity": 10})
    await client.patch("/warehouses/1", json={"name": "Переименован"})
    await seed()
    assert await balance(1, 1) == (0, 0)
    assert await count(Product) == 3 and await count(Warehouse) == 2
    assert await count(StockMovement) == 5


async def test_seed_preserves_nonempty_database(client, inventory):
    await seed()
    assert await count(Product) == 1 and await count(Warehouse) == 2
    assert await balance(*inventory[:2]) == (10, 0)
    assert await count(StockMovement) == 1


async def test_static_ui_and_openapi(client):
    assert (await client.get("/")).headers["location"] == "/ui/"
    for path, content in (("/ui/", "CheckStock"), ("/ui/app.js", "refreshAll"), ("/ui/styles.css", "sidebar")):
        response = await client.get(path)
        assert response.status_code == 200 and content in response.text
    assert "/products" in (await client.get("/openapi.json")).json()["paths"]


async def race(client, requests, model, row_id):
    tasks = []
    try:
        async with AsyncSessionLocal() as session, session.begin():
            lock = select(model).where(model.id == row_id).with_for_update() if model else text(
                "SELECT pg_advisory_xact_lock(:key)"
            ).bindparams(key=row_id)
            await session.execute(lock)
            tasks = [asyncio.create_task(client.post(path, **options)) for path, options in requests]
            # Both independent requests must actually wait on PostgreSQL before release.
            async with asyncio.timeout(10):
                while True:
                    await session.execute(text("SELECT pg_stat_clear_snapshot()"))
                    waiting = await session.scalar(text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                        "AND pid <> pg_backend_pid() AND wait_event_type = 'Lock'"
                    ))
                    if waiting >= len(tasks):
                        break
                    await asyncio.sleep(0.01)
        return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_concurrent_reservations_of_last_units(client, inventory):
    request = ("/fbs/reservations", {"json": payload(inventory, 7)})
    responses = await race(client, [request, request], Warehouse, inventory[1])
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert await balance(*inventory[:2]) == (10, 7)
    assert await count(FBSReservation) == 1 and await count(StockMovement) == 2


async def test_concurrent_different_shipments(client, inventory):
    responses = await race(client, [
        ("/fbo/shipments", {"json": payload(inventory, 7)}),
        ("/transfers", {"json": payload(inventory, 7, True)}),
    ], Warehouse, inventory[1])
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert await balance(*inventory[:2]) == (3, 0)
    assert await count(FBOShipment) + await count(Transfer) == 1
    assert await count(StockMovement) == 2


@pytest.mark.parametrize("action", ["ship", "cancel", "deliver"])
async def test_concurrent_fbs_confirmation(client, inventory, action):
    operation = await create(client, "/fbs/reservations", payload(inventory, 4))
    if action == "deliver":
        assert (await client.post(f"/fbs/reservations/{operation}/ship")).status_code == 200
    request = (f"/fbs/reservations/{operation}/{action}", {})
    responses = await race(client, [request, request], FBSReservation, operation)
    assert [r.status_code for r in responses] == [200, 200]
    assert await balance(*inventory[:2]) == ((10, 0) if action == "cancel" else (6, 0))
    assert await count(StockMovement) == (4 if action == "deliver" else 3)


async def test_concurrent_ship_and_cancel(client, inventory):
    operation = await create(client, "/fbs/reservations", payload(inventory, 4))
    responses = await race(client, [
        (f"/fbs/reservations/{operation}/ship", {}),
        (f"/fbs/reservations/{operation}/cancel", {}),
    ], FBSReservation, operation)
    assert sorted(r.status_code for r in responses) == [200, 409]
    shipped = responses[0].status_code == 200
    assert await balance(*inventory[:2]) == ((6, 0) if shipped else (10, 0))
    assert await count(StockMovement) == 3


@pytest.mark.parametrize("path,model", [("/transfers", Transfer), ("/fbo/shipments", FBOShipment)])
async def test_concurrent_receives(client, inventory, path, model):
    operation = await create(client, path, payload(inventory, 4, path == "/transfers"))
    request = (f"{path}/{operation}/receive", {})
    responses = await race(client, [request, request], model, operation)
    assert [r.status_code for r in responses] == [200, 200]
    assert await balance(*inventory[:2]) == (6, 0)
    assert await balance(inventory[0], inventory[2]) == ((4, 0) if path == "/transfers" else (0, 0))
    assert await count(StockMovement) == 3


async def test_concurrent_first_receipts(client, inventory):
    product, _, south = inventory
    request = ("/receipts", {"json": dict(product_id=product, warehouse_id=south, quantity=3)})
    responses = await race(client, [request, request], Warehouse, south)
    assert [r.status_code for r in responses] == [201, 201]
    assert await balance(product, south) == (6, 0)
    assert await count(Stock) == 2 and await count(StockMovement) == 3


async def test_concurrent_warehouse_name_creation(client, inventory):
    request = ("/warehouses", {"json": {"name": "Запад"}})
    responses = await race(client, [request, request], None, 101104)
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert await count(Warehouse) == 3


async def test_concurrent_seed(client):
    await asyncio.gather(seed(), seed())
    assert await count(Product) == 3 and await count(Warehouse) == 2
    assert await count(StockMovement) == 4
    rows = (await client.get("/stocks")).json()
    assert sum(row["physical_quantity"] for row in rows) == 25


@pytest.mark.parametrize("operation", ["receipt", "reserve", "fbo", "transfer", "ship", "cancel", "deliver", "fbo_receive", "transfer_receive"])
async def test_history_failure_rolls_back_everything(client, inventory, operation):
    path = {"receipt": "/receipts", "reserve": "/fbs/reservations", "fbo": "/fbo/shipments", "transfer": "/transfers"}.get(operation)
    model = None
    previous_status = None
    if operation in ("ship", "cancel", "deliver"):
        operation_id = await create(client, "/fbs/reservations", payload(inventory))
        if operation == "deliver":
            await client.post(f"/fbs/reservations/{operation_id}/ship")
        path = f"/fbs/reservations/{operation_id}/{operation}"
        model = FBSReservation
    elif operation in ("fbo_receive", "transfer_receive"):
        prefix = "/fbo/shipments" if operation == "fbo_receive" else "/transfers"
        operation_id = await create(client, prefix, payload(inventory, transfer=operation == "transfer_receive"))
        path = f"{prefix}/{operation_id}/receive"
        model = FBOShipment if operation == "fbo_receive" else Transfer
    if model:
        async with AsyncSessionLocal() as session:
            previous_status = (await session.get(model, operation_id)).status
    before = [await balance(inventory[0], w) for w in inventory[1:]]
    counts = [await count(m) for m in (StockMovement, FBSReservation, FBOShipment, Transfer)]

    def fail_history(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO stock_movements"):
            raise RuntimeError("simulated history write failure")

    event.listen(engine.sync_engine, "before_cursor_execute", fail_history)
    try:
        with pytest.raises(RuntimeError, match="simulated history"):
            await client.post(path, **({"json": payload(inventory, transfer=operation == "transfer")} if not model else {}))
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fail_history)
    assert [await balance(inventory[0], w) for w in inventory[1:]] == before
    assert [await count(m) for m in (StockMovement, FBSReservation, FBOShipment, Transfer)] == counts
    if model:
        async with AsyncSessionLocal() as session:
            assert (await session.get(model, operation_id)).status == previous_status
