from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fbs_reservation import FBSReservation, FBSReservationStatus
from app.models.product import Product
from app.models.stock import Stock
from app.models.stock_movement import StockMovement, StockMovementType
from app.models.warehouse import Warehouse
from app.schemas.fbs import FBSReserveCreate


async def reserve_fbs(session: AsyncSession, data: FBSReserveCreate) -> FBSReservation:
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

    stock.reserved_quantity += data.quantity
    reservation = FBSReservation(
        product_id=data.product_id,
        warehouse_id=data.warehouse_id,
        quantity=data.quantity,
        status=FBSReservationStatus.RESERVED,
    )
    session.add(reservation)
    await session.flush()  # Получаем ID резерва, не завершая транзакцию.

    session.add(StockMovement(
        movement_type=StockMovementType.FBS_RESERVED,
        product_id=data.product_id,
        quantity=data.quantity,
        from_warehouse_id=data.warehouse_id,
        fbs_reservation_id=reservation.id,
    ))
    await session.flush()
    return reservation


async def _locked_reservation(session: AsyncSession, reservation_id: int) -> FBSReservation:
    reservation = (
        await session.execute(
            select(FBSReservation)
            .where(FBSReservation.id == reservation_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if reservation is None:
        raise HTTPException(status_code=404, detail="Резерв FBS не найден")
    return reservation


async def _locked_stock(session: AsyncSession, reservation: FBSReservation) -> Stock:
    stock = (
        await session.execute(
            select(Stock)
            .where(
                Stock.product_id == reservation.product_id,
                Stock.warehouse_id == reservation.warehouse_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=409, detail="Не найден остаток для данного резерва")
    return stock


async def cancel_fbs(session: AsyncSession, reservation_id: int) -> FBSReservation:
    reservation = await _locked_reservation(session, reservation_id)
    if reservation.status == FBSReservationStatus.CANCELLED:
        return reservation  # Повторная отмена ничего не меняет.
    if reservation.status != FBSReservationStatus.RESERVED:
        raise HTTPException(status_code=409, detail="Отменить можно только неотправленный резерв")

    stock = await _locked_stock(session, reservation)
    if stock.reserved_quantity < reservation.quantity:
        raise HTTPException(status_code=409, detail="Резерв и остатки не согласованы")

    stock.reserved_quantity -= reservation.quantity
    reservation.status = FBSReservationStatus.CANCELLED
    reservation.cancelled_at = datetime.now(timezone.utc)
    session.add(StockMovement(
        movement_type=StockMovementType.FBS_CANCELLED,
        product_id=reservation.product_id,
        quantity=reservation.quantity,
        to_warehouse_id=reservation.warehouse_id,
        fbs_reservation_id=reservation.id,
    ))
    await session.flush()
    return reservation


async def ship_fbs(session: AsyncSession, reservation_id: int) -> FBSReservation:
    reservation = await _locked_reservation(session, reservation_id)
    if reservation.status in (FBSReservationStatus.SHIPPED, FBSReservationStatus.DELIVERED):
        return reservation  # Не списываем второй раз.
    if reservation.status != FBSReservationStatus.RESERVED:
        raise HTTPException(status_code=409, detail="Отправить можно только активный резерв")

    stock = await _locked_stock(session, reservation)
    if stock.reserved_quantity < reservation.quantity or stock.physical_quantity < reservation.quantity:
        raise HTTPException(status_code=409, detail="Резерв и остатки не согласованы")

    stock.physical_quantity -= reservation.quantity
    stock.reserved_quantity -= reservation.quantity
    reservation.status = FBSReservationStatus.SHIPPED
    reservation.shipped_at = datetime.now(timezone.utc)
    session.add(StockMovement(
        movement_type=StockMovementType.FBS_SHIPPED,
        product_id=reservation.product_id,
        quantity=reservation.quantity,
        from_warehouse_id=reservation.warehouse_id,
        fbs_reservation_id=reservation.id,
    ))
    await session.flush()
    return reservation


async def deliver_fbs(session: AsyncSession, reservation_id: int) -> FBSReservation:
    reservation = await _locked_reservation(session, reservation_id)
    if reservation.status == FBSReservationStatus.DELIVERED:
        return reservation  # Повторное подтверждение ничего не меняет.
    if reservation.status != FBSReservationStatus.SHIPPED:
        raise HTTPException(status_code=409, detail="Подтвердить доставку можно только после отправки")

    reservation.status = FBSReservationStatus.DELIVERED
    reservation.delivered_at = datetime.now(timezone.utc)
    session.add(StockMovement(
        movement_type=StockMovementType.FBS_DELIVERED,
        product_id=reservation.product_id,
        quantity=reservation.quantity,
        from_warehouse_id=reservation.warehouse_id,
        fbs_reservation_id=reservation.id,
    ))
    await session.flush()
    return reservation
