from fastapi import HTTPException
from sqlalchemy import and_, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.stock import Stock
from app.models.stock_movement import StockMovement, StockMovementType
from app.models.warehouse import Warehouse
from app.schemas.stocks import StockOverview

async def receive_stock(
    session: AsyncSession,
    product_id: int,
    warehouse_id: int,
    quantity: int,
) -> Stock:

    if quantity <= 0:
        raise HTTPException(status_code=422, detail="Количество должно быть больше нуля")

    product = await session.get(Product, product_id)
    
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")

    warehouse = await session.get(Warehouse, warehouse_id, with_for_update=True)
    
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Склад не найден")
    
    if not warehouse.is_active:
        raise HTTPException(status_code=409, detail="Нельзя принять товар на архивный склад")

    # Одно атомарное действие: создать строку остатка или увеличить существующую.
    # ON CONFLICT защищает от дублирования строки при параллельных приходах.
    statement = (
        insert(Stock)
        .values(
            product_id=product_id,
            warehouse_id=warehouse_id,
            physical_quantity=quantity,
            reserved_quantity=0,
        )
        .on_conflict_do_update(
            constraint="uq_product_warehouse",
            set_={"physical_quantity": Stock.physical_quantity + quantity},
        )
        .returning(Stock.id)
    )
    stock_id = (await session.execute(statement)).scalar_one()

    session.add(
        StockMovement(
            movement_type=StockMovementType.RECEIPT,
            product_id=product_id,
            quantity=quantity,
            to_warehouse_id=warehouse_id,
        )
    )
    await session.flush()

    # Получаем актуальный остаток, даже если объект раньше уже был в сессии.
    return (
        await session.execute(
            select(Stock)
            .where(Stock.id == stock_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()


def _to_overview(product: Product, warehouse: Warehouse, stock: Stock | None) -> StockOverview:
    return StockOverview(
        id=stock.id if stock is not None else None,
        product_id=product.id,
        warehouse_id=warehouse.id,
        physical_quantity=stock.physical_quantity if stock is not None else 0,
        reserved_quantity=stock.reserved_quantity if stock is not None else 0,
        sku=product.sku,
        product_name=product.name,
        warehouse_name=warehouse.name,
        warehouse_is_active=warehouse.is_active,
    )


async def list_stocks(session: AsyncSession, product_id: int | None = None) -> list[StockOverview]:
    """Показывает каждый товар на каждом ФФ, включая нулевые остатки."""
    if product_id is not None and await session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Товар не найден")

    query = (
        select(Product, Warehouse, Stock)
        .select_from(Product)
        .join(Warehouse, true())
        .outerjoin(
            Stock,
            and_(Stock.product_id == Product.id, Stock.warehouse_id == Warehouse.id),
        )
        .order_by(Product.sku, Warehouse.name)
    )
    if product_id is not None:
        query = query.where(Product.id == product_id)

    rows = (await session.execute(query)).all()
    return [_to_overview(product, warehouse, stock) for product, warehouse, stock in rows]
