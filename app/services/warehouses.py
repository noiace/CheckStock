from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.warehouse import Warehouse


def _clean_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Название склада не должно быть пустым")
    return name


async def list_warehouses(session: AsyncSession, active_only: bool = False) -> list[Warehouse]:
    query = select(Warehouse).order_by(Warehouse.id)
    if active_only:
        query = query.where(Warehouse.is_active.is_(True))
    return list((await session.scalars(query)).all())


async def get_warehouse(session: AsyncSession, warehouse_id: int) -> Warehouse:
    warehouse = await session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Склад не найден")
    return warehouse


async def _ensure_unique_active_name(
    session: AsyncSession, name: str, exclude_id: int | None = None
) -> None:
    query = select(Warehouse.id).where(
        Warehouse.is_active.is_(True), func.lower(Warehouse.name) == name.lower()
    )
    if exclude_id is not None:
        query = query.where(Warehouse.id != exclude_id)
    if (await session.scalar(query)) is not None:
        raise HTTPException(status_code=409, detail="Активный склад с таким названием уже существует")


async def create_warehouse(session: AsyncSession, name: str) -> Warehouse:
    name = _clean_name(name)
    await _ensure_unique_active_name(session, name)
    warehouse = Warehouse(name=name, is_active=True)
    session.add(warehouse)
    await session.flush()
    return warehouse


async def rename_warehouse(session: AsyncSession, warehouse_id: int, name: str) -> Warehouse:
    warehouse = await session.get(Warehouse, warehouse_id, with_for_update=True)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Склад не найден")
    if not warehouse.is_active:
        raise HTTPException(status_code=409, detail="Архивный склад переименовывать нельзя")
    name = _clean_name(name)
    await _ensure_unique_active_name(session, name, exclude_id=warehouse_id)
    warehouse.name = name
    await session.flush()
    return warehouse


async def archive_warehouse(session: AsyncSession, warehouse_id: int) -> Warehouse:
    warehouse = await session.get(Warehouse, warehouse_id, with_for_update=True)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Склад не найден")
    # Удаление только логическое: остатки, отправки и история остаются в базе.
    warehouse.is_active = False
    await session.flush()
    return warehouse
