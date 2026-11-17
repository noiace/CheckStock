from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.product import Product
from models.stock import Stock
from models.stock_movement import StockMovement, StockMovementType
from models.transfer import Transfer, TransferStatus
from models.warehouse import Warehouse
from schemas.transfers import TransferCreate


async def create_transfer(session: AsyncSession, data: TransferCreate) -> Transfer:
    if data.from_warehouse_id == data.to_warehouse_id:
        raise HTTPException(status_code=422, detail="Склад отправления и назначения должны различаться")
    if await session.get(Product, data.product_id) is None:
        raise HTTPException(status_code=404, detail="Товар не найден")

    # Блокируем склады в одном порядке, чтобы не конфликтовать с архивированием.
    warehouses = (
        await session.scalars(
            select(Warehouse)
            .where(Warehouse.id.in_([data.from_warehouse_id, data.to_warehouse_id]))
            .order_by(Warehouse.id)
            .with_for_update()
        )
    ).all()
    by_id = {warehouse.id: warehouse for warehouse in warehouses}
    source = by_id.get(data.from_warehouse_id)
    destination = by_id.get(data.to_warehouse_id)
    if source is None or destination is None:
        raise HTTPException(status_code=404, detail="Склад отправления или назначения не найден")
    if not source.is_active or not destination.is_active:
        raise HTTPException(status_code=409, detail="Нельзя создать перемещение с архивным складом")

    stock = (
        await session.scalars(
            select(Stock)
            .where(
                Stock.product_id == data.product_id,
                Stock.warehouse_id == data.from_warehouse_id,
            )
            .with_for_update()
        )
    ).one_or_none()
    if stock is None or stock.physical_quantity - stock.reserved_quantity < data.quantity:
        raise HTTPException(status_code=409, detail="Недостаточно доступного остатка на складе отправления")

    stock.physical_quantity -= data.quantity
    transfer = Transfer(
        product_id=data.product_id,
        from_warehouse_id=data.from_warehouse_id,
        to_warehouse_id=data.to_warehouse_id,
        quantity=data.quantity,
        status=TransferStatus.IN_TRANSIT,
    )
    session.add(transfer)
    await session.flush()

    session.add(StockMovement(
        movement_type=StockMovementType.TRANSFER_SHIPPED,
        product_id=data.product_id,
        quantity=data.quantity,
        from_warehouse_id=data.from_warehouse_id,
        to_warehouse_id=data.to_warehouse_id,
        transfer_id=transfer.id,
    ))
    await session.flush()
    return transfer


async def receive_transfer(session: AsyncSession, transfer_id: int) -> Transfer:
    transfer = (
        await session.scalars(
            select(Transfer).where(Transfer.id == transfer_id).with_for_update()
        )
    ).one_or_none()
    if transfer is None:
        raise HTTPException(status_code=404, detail="Перемещение не найдено")
    if transfer.status == TransferStatus.RECEIVED:
        return transfer  # Повторная приёмка не меняет остатки и историю.
    if transfer.status != TransferStatus.IN_TRANSIT:
        raise HTTPException(status_code=409, detail="Некорректный статус перемещения")

    destination = await session.get(Warehouse, transfer.to_warehouse_id, with_for_update=True)
    if destination is None:
        raise HTTPException(status_code=404, detail="Склад назначения не найден")

    await session.execute(
        insert(Stock)
        .values(
            product_id=transfer.product_id,
            warehouse_id=transfer.to_warehouse_id,
            physical_quantity=transfer.quantity,
            reserved_quantity=0,
        )
        .on_conflict_do_update(
            constraint="uq_product_warehouse",
            set_={"physical_quantity": Stock.physical_quantity + transfer.quantity},
        )
    )

    transfer.status = TransferStatus.RECEIVED
    transfer.received_at = datetime.now(timezone.utc)
    session.add(StockMovement(
        movement_type=StockMovementType.TRANSFER_RECEIVED,
        product_id=transfer.product_id,
        quantity=transfer.quantity,
        from_warehouse_id=transfer.from_warehouse_id,
        to_warehouse_id=transfer.to_warehouse_id,
        transfer_id=transfer.id,
    ))
    await session.flush()
    return transfer


async def list_transfers(session: AsyncSession, in_transit_only: bool = False) -> list[Transfer]:
    query = select(Transfer).order_by(Transfer.created_at.desc(), Transfer.id.desc())
    if in_transit_only:
        query = query.where(Transfer.status == TransferStatus.IN_TRANSIT)
    return list((await session.scalars(query)).all())


async def get_transfer(session: AsyncSession, transfer_id: int) -> Transfer:
    transfer = await session.get(Transfer, transfer_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail="Перемещение не найдено")
    return transfer
