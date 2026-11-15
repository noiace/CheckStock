from fastapi import APIRouter
from pydantic import BaseModel
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

warehouses_router = APIRouter()

@warehouses_router.get("/warehouses", tags=["warehouses"], name="Get all warehouses")
async def GetAllWarehouses():
    pass

@warehouses_router.get("/warehouse/", tags=["warehouses"], name="Get warehouse by id")
async def GetWarehouse():
    pass

@warehouses_router.post("/warehouses", tags=["warehouses"], name="Add new warehouse")
async def AddNewWarehouse():
    pass

@warehouses_router.patch("/warehouses", tags=["warehouses"], name="Rename warehouse")
async def RenameWarehouse():
    pass

@warehouses_router.delete("/warehouses", tags=["warehouses"], name="Remove warehouse by id")
async def RemoveWarehouse():
    pass