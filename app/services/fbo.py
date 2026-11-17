from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.fbo_shipment import FBOShipment, FBOShipmentStatus
from models.product import Product
from models.stock import Stock
from models.stock_movement import StockMovement, StockMovementType
from models.warehouse import Warehouse
from schemas.fbo import FBOShipmentCreate


async def ship_fbo(session: AsyncSession, data: FBOShipmentCreate) -> FBOShipment:
    if await session.get(Product, data.product_id) is None:
        raise HTTPException(status_code=404, detail="Товар не найден")

    warehouse = await session.get(Warehouse, data.warehouse_id, with_for_update=True)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Склад не найден")
    if not warehouse.is_active:
        raise HTTPException(status_code=409, detail="Склад находится в архиве")

    stock = (
        await session.execute(
            select(Stock)
            .where(Stock.product_id == data.product_id, Stock.warehouse_id == data.warehouse_id)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if stock is None or stock.physical_quantity - stock.reserved_quantity < data.quantity:
        raise HTTPException(status_code=409, detail="Недостаточно доступного остатка на выбранном складе")

    stock.physical_quantity -= data.quantity
    shipment = FBOShipment(
        product_id=data.product_id,
        warehouse_id=data.warehouse_id,
        quantity=data.quantity,
        status=FBOShipmentStatus.IN_TRANSIT,
    )
    session.add(shipment)
    await session.flush()

    session.add(StockMovement(
        movement_type=StockMovementType.FBO_SHIPPED,
        product_id=data.product_id,
        quantity=data.quantity,
        from_warehouse_id=data.warehouse_id,
        fbo_shipment_id=shipment.id,
    ))
    await session.flush()
    return shipment


async def receive_fbo(session: AsyncSession, shipment_id: int) -> FBOShipment:
    shipment = (
        await session.execute(
            select(FBOShipment)
            .where(FBOShipment.id == shipment_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Отправка FBO не найдена")
    if shipment.status == FBOShipmentStatus.RECEIVED:
        return shipment  # Повторная приёмка не меняет остатки.
    if shipment.status != FBOShipmentStatus.IN_TRANSIT:
        raise HTTPException(status_code=409, detail="Некорректный статус отправки FBO")

    shipment.status = FBOShipmentStatus.RECEIVED
    shipment.received_at = datetime.now(timezone.utc)
    session.add(StockMovement(
        movement_type=StockMovementType.FBO_RECEIVED,
        product_id=shipment.product_id,
        quantity=shipment.quantity,
        from_warehouse_id=shipment.warehouse_id,
        fbo_shipment_id=shipment.id,
    ))
    await session.flush()
    return shipment
