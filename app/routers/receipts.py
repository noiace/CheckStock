from fastapi import APIRouter
from pydantic import BaseModel
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

receipts_router = APIRouter()

@receipts_router.post("/receipts", tags=["receipts"], name="")
async def receipt():
    pass