from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.fbs import FBSReserveCreate, FBSReservationRead
from app.services import fbs as service

fbs_router = APIRouter(prefix="/fbs/reservations", tags=["fbs"])


@fbs_router.post("", response_model=FBSReservationRead, status_code=status.HTTP_201_CREATED)
async def reserve_product(data: FBSReserveCreate, session: AsyncSession = Depends(get_db)):
    async with session.begin():
        result = await service.reserve_fbs(session, data)
        response = FBSReservationRead.model_validate(result)
    return response


@fbs_router.post("/{id}/cancel", response_model=FBSReservationRead)
async def cancel_reservation(id: int = Path(gt=0), session: AsyncSession = Depends(get_db)):
    async with session.begin():
        result = await service.cancel_fbs(session, id)
        response = FBSReservationRead.model_validate(result)
    return response


@fbs_router.post("/{id}/ship", response_model=FBSReservationRead)
async def ship_reservation(id: int = Path(gt=0), session: AsyncSession = Depends(get_db)):
    async with session.begin():
        result = await service.ship_fbs(session, id)
        response = FBSReservationRead.model_validate(result)
    return response


@fbs_router.post("/{id}/deliver", response_model=FBSReservationRead)
async def deliver_reservation(id: int = Path(gt=0), session: AsyncSession = Depends(get_db)):
    async with session.begin():
        result = await service.deliver_fbs(session, id)
        response = FBSReservationRead.model_validate(result)
    return response
