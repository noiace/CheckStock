from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.transfer import TransferStatus


class TransferCreate(BaseModel):
    product_id: int = Field(gt=0)
    from_warehouse_id: int = Field(gt=0)
    to_warehouse_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class TransferRead(BaseModel):
    id: int
    product_id: int
    from_warehouse_id: int
    to_warehouse_id: int
    quantity: int
    status: TransferStatus
    created_at: datetime
    received_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
