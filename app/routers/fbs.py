from fastapi import APIRouter
from pydantic import BaseModel
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

fbs_router = APIRouter()

@fbs_router.post("/fbs/reservations", tags=["fbs"], name="FBS reserve product")
async def ReserveProduct():
    pass

@fbs_router.post("/fbs/reservations/{id}/cancel", tags=["fbs"], name="Cancel reserve product")
async def CancelReserveProduct():
    pass

@fbs_router.post("/fbs/reservations/{id}/ship", tags=["fbs"], name="Ship reserve product")
async def ShipReserveProduct():
    pass

@fbs_router.post("/fbs/reservations/{id}/deliver", tags=["fbs"], name="deliver product")
async def DeliverProduct():
    pass
