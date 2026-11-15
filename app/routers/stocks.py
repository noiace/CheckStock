from fastapi import APIRouter
from pydantic import BaseModel
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

stocks_router = APIRouter()

@stocks_router.get("/stocks", tags=["stocks"], name="Get all stock products")
async def GetAllStockProducts():
    pass

@stocks_router.get("/stocks", tags=["stocks"], name="Get stock product by id")
async def GetStockProduct():
    pass
