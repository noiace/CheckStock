from fastapi import APIRouter
from pydantic import BaseModel
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

fbo_router = APIRouter()

@fbo_router.post("/fbo/shipments", tags=["fbo"], name="")
async def ShipProduct():
    pass

@fbo_router.post("/fbo/shipments/{id}/receive", tags=["fbo"], name="")
async def ReceiveProduct():
    pass
