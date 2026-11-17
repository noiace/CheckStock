from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from schemas.transfers import TransferCreate, TransferRead
from services import transfers as service

transfers_router = APIRouter(prefix="/transfers", tags=["transfers"])


@transfers_router.get("", response_model=list[TransferRead])
async def list_transfers(in_transit_only: bool = False, session: AsyncSession = Depends(get_db)):
    return await service.list_transfers(session, in_transit_only=in_transit_only)


@transfers_router.get("/{id}", response_model=TransferRead)
async def get_transfer(id: int = Path(gt=0), session: AsyncSession = Depends(get_db)):
    return await service.get_transfer(session, id)


@transfers_router.post("", response_model=TransferRead, status_code=status.HTTP_201_CREATED)
async def create_transfer(data: TransferCreate, session: AsyncSession = Depends(get_db)):
    async with session.begin():
        transfer = await service.create_transfer(session, data)
        response = TransferRead.model_validate(transfer)
    return response


@transfers_router.post("/{id}/receive", response_model=TransferRead)
async def receive_transfer(id: int = Path(gt=0), session: AsyncSession = Depends(get_db)):
    async with session.begin():
        transfer = await service.receive_transfer(session, id)
        response = TransferRead.model_validate(transfer)
    return response
