from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.stock_movement import StockMovementType
from schemas.movements import StockMovementRead, TransitItemRead
from services import movements as service

movements_router = APIRouter(tags=["movements"])


@movements_router.get("/movements", response_model=list[StockMovementRead])
async def get_history_movements(
    product_id: int | None = Query(default=None, gt=0),
    warehouse_id: int | None = Query(default=None, gt=0),
    movement_type: StockMovementType | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    return await service.list_movements(
        session, product_id=product_id, warehouse_id=warehouse_id,
        movement_type=movement_type, limit=limit, offset=offset,
    )


@movements_router.get("/movements/in-transit", response_model=list[TransitItemRead])
async def get_in_transit(session: AsyncSession = Depends(get_db)):
    return await service.list_in_transit(session)
