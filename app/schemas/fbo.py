from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.fbo_shipment import FBOShipmentStatus


class FBOShipmentCreate(BaseModel):
    product_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class FBOShipmentRead(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    quantity: int
    status: FBOShipmentStatus
    created_at: datetime
    received_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
