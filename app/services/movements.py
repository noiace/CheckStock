from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fbo_shipment import FBOShipment, FBOShipmentStatus
from app.models.fbs_reservation import FBSReservation, FBSReservationStatus
from app.models.stock_movement import StockMovement, StockMovementType
from app.models.transfer import Transfer, TransferStatus
from app.schemas.movements import TransitItemRead


async def list_movements(
    session: AsyncSession,
    product_id: int | None = None,
    warehouse_id: int | None = None,
    movement_type: StockMovementType | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[StockMovement]:
    query = select(StockMovement)
    if product_id is not None:
        query = query.where(StockMovement.product_id == product_id)
    if warehouse_id is not None:
        query = query.where(or_(
            StockMovement.from_warehouse_id == warehouse_id,
            StockMovement.to_warehouse_id == warehouse_id,
        ))
    if movement_type is not None:
        query = query.where(StockMovement.movement_type == movement_type)
    query = query.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
    query = query.limit(limit).offset(offset)
    return list((await session.scalars(query)).all())


async def list_in_transit(session: AsyncSession) -> list[TransitItemRead]:
    transfers = (await session.scalars(
        select(Transfer).where(Transfer.status == TransferStatus.IN_TRANSIT)
    )).all()
    fbo_shipments = (await session.scalars(
        select(FBOShipment).where(FBOShipment.status == FBOShipmentStatus.IN_TRANSIT)
    )).all()
    fbs_shipments = (await session.scalars(
        select(FBSReservation).where(FBSReservation.status == FBSReservationStatus.SHIPPED)
    )).all()

    items = [
        TransitItemRead(
            kind="TRANSFER", operation_id=t.id, product_id=t.product_id,
            quantity=t.quantity, from_warehouse_id=t.from_warehouse_id,
            to_warehouse_id=t.to_warehouse_id, created_at=t.created_at,
        )
        for t in transfers
    ]
    items += [
        TransitItemRead(
            kind="FBO", operation_id=s.id, product_id=s.product_id,
            quantity=s.quantity, from_warehouse_id=s.warehouse_id,
            to_warehouse_id=None, created_at=s.created_at,
        )
        for s in fbo_shipments
    ]
    items += [
        TransitItemRead(
            kind="FBS", operation_id=r.id, product_id=r.product_id,
            quantity=r.quantity, from_warehouse_id=r.warehouse_id,
            to_warehouse_id=None, created_at=r.shipped_at or r.created_at,
        )
        for r in fbs_shipments
    ]
    return sorted(items, key=lambda item: (item.created_at, item.operation_id), reverse=True)
