from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.fbo import FBOShipmentCreate, FBOShipmentRead
from app.services import fbo as service

fbo_router = APIRouter(prefix="/fbo/shipments", tags=["fbo"])


@fbo_router.post("", response_model=FBOShipmentRead, status_code=status.HTTP_201_CREATED)
async def create_shipment(data: FBOShipmentCreate, session: AsyncSession = Depends(get_db)):
    async with session.begin():
        result = await service.ship_fbo(session, data)
        response = FBOShipmentRead.model_validate(result)
    return response


@fbo_router.post("/{id}/receive", response_model=FBOShipmentRead)
async def receive_shipment(id: int = Path(gt=0), session: AsyncSession = Depends(get_db)):
    async with session.begin():
        result = await service.receive_fbo(session, id)
        response = FBOShipmentRead.model_validate(result)
    return response
