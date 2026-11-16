from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.stocks import StockOverview
from app.services.inventory import list_stocks

stocks_router = APIRouter()

@stocks_router.get("/stocks", response_model=list[StockOverview], tags=["stocks"])
async def get_all_stocks(session: AsyncSession = Depends(get_db)) -> list[StockOverview]:
    return await list_stocks(session)

@stocks_router.get("/stocks/{product_id}", response_model=list[StockOverview], tags=["stocks"])
async def get_product_stocks(
    product_id: int,
    session: AsyncSession = Depends(get_db),
) -> list[StockOverview]:
    return await list_stocks(session, product_id=product_id)
