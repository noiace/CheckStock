from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.fbs_reservation import FBSReservationStatus


class FBSReserveCreate(BaseModel):
    product_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class FBSReservationRead(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    quantity: int
    status: FBSReservationStatus
    created_at: datetime
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
