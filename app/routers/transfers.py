from fastapi import APIRouter
from pydantic import BaseModel
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

transfers_router = APIRouter()

@transfers_router.post("/transfers", tags=["transfers"], name="")
async def CreateTransfer():
    pass

@transfers_router.post("/transfers/{id}/receive", tags=["transfers"], name="")
async def TransferRecieveProduct():
    pass
