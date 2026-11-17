from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.stock_movement import StockMovementType


class StockMovementRead(BaseModel):
    id: int
    movement_type: StockMovementType
    product_id: int
    quantity: int
    from_warehouse_id: int | None
    to_warehouse_id: int | None
    fbs_reservation_id: int | None
    fbo_shipment_id: int | None
    transfer_id: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransitItemRead(BaseModel):
    kind: Literal["TRANSFER", "FBO", "FBS"]
    operation_id: int
    product_id: int
    quantity: int = Field(gt=0)
    from_warehouse_id: int
    to_warehouse_id: int | None
    created_at: datetime
