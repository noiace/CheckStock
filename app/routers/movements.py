from fastapi import APIRouter
from pydantic import BaseModel
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

movements_router = APIRouter()

@movements_router.get("/movements", tags=["movements"], name="")
async def GetHistoryMovements():
    pass