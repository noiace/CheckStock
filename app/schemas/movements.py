from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.stock_movement import StockMovementType


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
