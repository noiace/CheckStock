from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from schemas.warehouses import WarehouseCreate, WarehouseRead, WarehouseRename
from services import warehouses as service

warehouses_router = APIRouter(prefix="/warehouses", tags=["warehouses"])


@warehouses_router.get("", response_model=list[WarehouseRead])
async def get_warehouses(active_only: bool = False, session: AsyncSession = Depends(get_db)):
    return await service.list_warehouses(session, active_only=active_only)


@warehouses_router.get("/{id}", response_model=WarehouseRead)
async def get_warehouse(id: int = Path(gt=0), session: AsyncSession = Depends(get_db)):
    return await service.get_warehouse(session, id)


@warehouses_router.post("", response_model=WarehouseRead, status_code=status.HTTP_201_CREATED)
async def create_warehouse(data: WarehouseCreate, session: AsyncSession = Depends(get_db)):
    async with session.begin():
        warehouse = await service.create_warehouse(session, data.name)
        response = WarehouseRead.model_validate(warehouse)
    return response


@warehouses_router.patch("/{id}", response_model=WarehouseRead)
async def rename_warehouse(data: WarehouseRename, id: int = Path(gt=0), session: AsyncSession = Depends(get_db)):
    async with session.begin():
        warehouse = await service.rename_warehouse(session, id, data.name)
        response = WarehouseRead.model_validate(warehouse)
    return response


@warehouses_router.delete("/{id}", response_model=WarehouseRead)
async def archive_warehouse(id: int = Path(gt=0), session: AsyncSession = Depends(get_db)):
    async with session.begin():
        warehouse = await service.archive_warehouse(session, id)
        response = WarehouseRead.model_validate(warehouse)
    return response
