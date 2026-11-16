from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.receipts import ReceiptCreate
from app.schemas.stocks import StockRead
from app.services.inventory import receive_stock

receipts_router = APIRouter()

@receipts_router.post(
    "/receipts", response_model=StockRead, status_code=status.HTTP_201_CREATED, tags=["receipts"]
)
async def receipt(data: ReceiptCreate, session: AsyncSession = Depends(get_db)) -> StockRead:
    # Остаток и запись в историю сохраняются одной транзакцией.
    async with session.begin():
        stock = await receive_stock(
            session, product_id=data.product_id,
            warehouse_id=data.warehouse_id, quantity=data.quantity,
        )
        result = StockRead.model_validate(stock)
    return result
